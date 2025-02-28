import time
from threading import Event
from typing import Any
from typing import cast

from slack_sdk import WebClient
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
from sqlalchemy.orm import Session

from danswer.configs.constants import MessageType
from danswer.configs.danswerbot_configs import DANSWER_BOT_RESPOND_EVERY_CHANNEL
from danswer.configs.danswerbot_configs import NOTIFY_SLACKBOT_NO_ANSWER
from danswer.configs.model_configs import ENABLE_RERANKING_ASYNC_FLOW
from danswer.danswerbot.slack.config import get_slack_bot_config_for_channel
from danswer.danswerbot.slack.constants import SLACK_CHANNEL_ID
from danswer.danswerbot.slack.handlers.handle_feedback import handle_slack_feedback
from danswer.danswerbot.slack.handlers.handle_message import handle_message
from danswer.danswerbot.slack.models import SlackMessageInfo
from danswer.danswerbot.slack.tokens import fetch_tokens
from danswer.danswerbot.slack.utils import ChannelIdAdapter
from danswer.danswerbot.slack.utils import decompose_block_id
from danswer.danswerbot.slack.utils import get_channel_name_from_id
from danswer.danswerbot.slack.utils import get_danswer_bot_app_id
from danswer.danswerbot.slack.utils import read_slack_thread
from danswer.danswerbot.slack.utils import remove_danswer_bot_tag
from danswer.danswerbot.slack.utils import respond_in_thread
from danswer.db.engine import get_sqlalchemy_engine
from danswer.dynamic_configs.interface import ConfigNotFoundError
from danswer.one_shot_answer.models import ThreadMessage
from danswer.search.search_nlp_models import warm_up_models
from danswer.server.manage.models import SlackBotTokens
from danswer.utils.logger import setup_logger


logger = setup_logger()


def prefilter_requests(req: SocketModeRequest, client: SocketModeClient) -> bool:
    """True to keep going, False to ignore this Slack request"""
    if req.type == "events_api":
        # Verify channel is valid
        event = cast(dict[str, Any], req.payload.get("event", {}))
        msg = cast(str | None, event.get("text"))
        channel = cast(str | None, event.get("channel"))
        channel_specific_logger = ChannelIdAdapter(
            logger, extra={SLACK_CHANNEL_ID: channel}
        )

        # This should never happen, but we can't continue without a channel since
        # we can't send a response without it
        if not channel:
            channel_specific_logger.error("Found message without channel - skipping")
            return False

        if not msg:
            channel_specific_logger.error("Cannot respond to empty message - skipping")
            return False

        # Ensure that the message is a new message of expected type
        event_type = event.get("type")
        if event_type not in ["app_mention", "message"]:
            channel_specific_logger.info(
                f"Ignoring non-message event of type '{event_type}' for channel '{channel}'"
            )
            return False

        if event_type == "message":
            bot_tag_id = get_danswer_bot_app_id(client.web_client)
            # DMs with the bot don't pick up the @DanswerBot so we have to keep the
            # caught events_api
            if bot_tag_id and bot_tag_id in msg and event.get("channel_type") != "im":
                # Let the tag flow handle this case, don't reply twice
                return False

        if event.get("bot_profile"):
            channel_specific_logger.info("Ignoring message from bot")
            return False

        # Ignore things like channel_join, channel_leave, etc.
        # NOTE: "file_share" is just a message with a file attachment, so we
        # should not ignore it
        message_subtype = event.get("subtype")
        if message_subtype not in [None, "file_share"]:
            channel_specific_logger.info(
                f"Ignoring message with subtype '{message_subtype}' since is is a special message type"
            )
            return False

        message_ts = event.get("ts")
        thread_ts = event.get("thread_ts")
        # Pick the root of the thread (if a thread exists)
        # Can respond in thread if it's an "im" directly to Danswer or @DanswerBot is tagged
        if (
            thread_ts
            and message_ts != thread_ts
            and event_type != "app_mention"
            and event.get("channel_type") != "im"
        ):
            channel_specific_logger.debug(
                "Skipping message since it is not the root of a thread"
            )
            return False

        msg = cast(str, event.get("text", ""))
        if not msg:
            channel_specific_logger.error("Unable to process empty message")
            return False

    if req.type == "slash_commands":
        # Verify that there's an associated channel
        channel = req.payload.get("channel_id")
        channel_specific_logger = ChannelIdAdapter(
            logger, extra={SLACK_CHANNEL_ID: channel}
        )
        if not channel:
            channel_specific_logger.error(
                "Received DanswerBot command without channel - skipping"
            )
            return False

        sender = req.payload.get("user_id")
        if not sender:
            channel_specific_logger.error(
                "Cannot respond to DanswerBot command without sender to respond to."
            )
            return False

    return True


def process_feedback(req: SocketModeRequest, client: SocketModeClient) -> None:
    actions = req.payload.get("actions")
    if not actions:
        logger.error("Unable to process block actions - no actions found")
        return

    action = cast(dict[str, Any], actions[0])
    action_id = cast(str, action.get("action_id"))
    block_id = cast(str, action.get("block_id"))
    user_id = cast(str, req.payload["user"]["id"])
    channel_id = cast(str, req.payload["container"]["channel_id"])
    thread_ts = cast(str, req.payload["container"]["thread_ts"])

    handle_slack_feedback(
        block_id=block_id,
        feedback_type=action_id,
        client=client.web_client,
        user_id_to_post_confirmation=user_id,
        channel_id_to_post_confirmation=channel_id,
        thread_ts_to_post_confirmation=thread_ts,
    )

    query_event_id, _, _ = decompose_block_id(block_id)
    logger.info(f"Successfully handled QA feedback for event: {query_event_id}")


def build_request_details(
    req: SocketModeRequest, client: SocketModeClient
) -> SlackMessageInfo:
    if req.type == "events_api":
        event = cast(dict[str, Any], req.payload["event"])
        msg = cast(str, event["text"])
        channel = cast(str, event["channel"])
        tagged = event.get("type") == "app_mention"
        message_ts = event.get("ts")
        thread_ts = event.get("thread_ts")

        msg = remove_danswer_bot_tag(msg, client=client.web_client)

        if tagged:
            logger.info("User tagged DanswerBot")

        if thread_ts != message_ts and thread_ts is not None:
            thread_messages = read_slack_thread(
                channel=channel, thread=thread_ts, client=client.web_client
            )
        else:
            thread_messages = [
                ThreadMessage(message=msg, sender=None, role=MessageType.USER)
            ]

        return SlackMessageInfo(
            thread_messages=thread_messages,
            channel_to_respond=channel,
            msg_to_respond=cast(str, message_ts or thread_ts),
            sender=event.get("user") or None,
            bipass_filters=tagged,
            is_bot_msg=False,
        )

    elif req.type == "slash_commands":
        channel = req.payload["channel_id"]
        msg = req.payload["text"]
        sender = req.payload["user_id"]

        single_msg = ThreadMessage(message=msg, sender=None, role=MessageType.USER)

        return SlackMessageInfo(
            thread_messages=[single_msg],
            channel_to_respond=channel,
            msg_to_respond=None,
            sender=sender,
            bipass_filters=True,
            is_bot_msg=True,
        )

    raise RuntimeError("Programming fault, this should never happen.")


def apologize_for_fail(
    details: SlackMessageInfo,
    client: SocketModeClient,
) -> None:
    respond_in_thread(
        client=client.web_client,
        channel=details.channel_to_respond,
        thread_ts=details.msg_to_respond,
        text="Sorry, we weren't able to find anything relevant :cold_sweat:",
    )


def process_message(
    req: SocketModeRequest,
    client: SocketModeClient,
    respond_every_channel: bool = DANSWER_BOT_RESPOND_EVERY_CHANNEL,
    notify_no_answer: bool = NOTIFY_SLACKBOT_NO_ANSWER,
) -> None:
    logger.debug(f"Received Slack request of type: '{req.type}'")

    # Throw out requests that can't or shouldn't be handled
    if not prefilter_requests(req, client):
        return

    details = build_request_details(req, client)
    channel = details.channel_to_respond
    channel_name, is_dm = get_channel_name_from_id(
        client=client.web_client, channel_id=channel
    )

    engine = get_sqlalchemy_engine()
    with Session(engine) as db_session:
        slack_bot_config = get_slack_bot_config_for_channel(
            channel_name=channel_name, db_session=db_session
        )

        # Be careful about this default, don't want to accidentally spam every channel
        # Users should be able to DM slack bot in their private channels though
        if (
            slack_bot_config is None
            and not respond_every_channel
            # Can't have configs for DMs so don't toss them out
            and not is_dm
            # If @DanswerBot or /DanswerBot, always respond with the default configs
            and not (details.is_bot_msg or details.bipass_filters)
        ):
            return

        failed = handle_message(
            message_info=details,
            channel_config=slack_bot_config,
            client=client.web_client,
        )

        # Skipping answering due to pre-filtering is not considered a failure
        if failed and notify_no_answer:
            apologize_for_fail(details, client)


def acknowledge_message(req: SocketModeRequest, client: SocketModeClient) -> None:
    response = SocketModeResponse(envelope_id=req.envelope_id)
    client.send_socket_mode_response(response)


def process_slack_event(client: SocketModeClient, req: SocketModeRequest) -> None:
    # Always respond right away, if Slack doesn't receive these frequently enough
    # it will assume the Bot is DEAD!!! :(
    acknowledge_message(req, client)

    try:
        if req.type == "interactive" and req.payload.get("type") == "block_actions":
            return process_feedback(req, client)

        elif req.type == "events_api" or req.type == "slash_commands":
            return process_message(req, client)
    except Exception:
        logger.exception("Failed to process slack event")


def _get_socket_client(slack_bot_tokens: SlackBotTokens) -> SocketModeClient:
    # For more info on how to set this up, checkout the docs:
    # https://docs.danswer.dev/slack_bot_setup
    return SocketModeClient(
        # This app-level token will be used only for establishing a connection
        app_token=slack_bot_tokens.app_token,
        web_client=WebClient(token=slack_bot_tokens.bot_token),
    )


def _initialize_socket_client(socket_client: SocketModeClient) -> None:
    socket_client.socket_mode_request_listeners.append(process_slack_event)  # type: ignore

    # Establish a WebSocket connection to the Socket Mode servers
    logger.info("Listening for messages from Slack...")
    socket_client.connect()


# Follow the guide (https://docs.danswer.dev/slack_bot_setup) to set up
# the slack bot in your workspace, and then add the bot to any channels you want to
# try and answer questions for. Running this file will setup Danswer to listen to all
# messages in those channels and attempt to answer them. As of now, it will only respond
# to messages sent directly in the channel - it will not respond to messages sent within a
# thread.
#
# NOTE: we are using Web Sockets so that you can run this from within a firewalled VPC
# without issue.
if __name__ == "__main__":
    warm_up_models(skip_cross_encoders=not ENABLE_RERANKING_ASYNC_FLOW)

    slack_bot_tokens: SlackBotTokens | None = None
    socket_client: SocketModeClient | None = None
    while True:
        try:
            latest_slack_bot_tokens = fetch_tokens()

            if latest_slack_bot_tokens != slack_bot_tokens:
                if slack_bot_tokens is not None:
                    logger.info("Slack Bot tokens have changed - reconnecting")
                slack_bot_tokens = latest_slack_bot_tokens
                # potentially may cause a message to be dropped, but it is complicated
                # to avoid + (1) if the user is changing tokens, they are likely okay with some
                # "migration downtime" and (2) if a single message is lost it is okay
                # as this should be a very rare occurrence
                if socket_client:
                    socket_client.close()

                socket_client = _get_socket_client(slack_bot_tokens)
                _initialize_socket_client(socket_client)

            # Let the handlers run in the background + re-check for token updates every 60 seconds
            Event().wait(timeout=60)
        except ConfigNotFoundError:
            # try again every 30 seconds. This is needed since the user may add tokens
            # via the UI at any point in the programs lifecycle - if we just allow it to
            # fail, then the user will need to restart the containers after adding tokens
            logger.debug(
                "Missing Slack Bot tokens - waiting 60 seconds and trying again"
            )
            if socket_client:
                socket_client.disconnect()
            time.sleep(60)
