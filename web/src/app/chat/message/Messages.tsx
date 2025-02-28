import {
  FiCheck,
  FiCopy,
  FiCpu,
  FiThumbsDown,
  FiThumbsUp,
  FiUser,
} from "react-icons/fi";
import { FeedbackType } from "../types";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { DanswerDocument } from "@/lib/search/interfaces";
import { SearchSummary, ShowHideDocsButton } from "./SearchSummary";
import { SourceIcon } from "@/components/SourceIcon";
import { ThreeDots } from "react-loader-spinner";

const Hoverable: React.FC<{ children: JSX.Element; onClick?: () => void }> = ({
  children,
  onClick,
}) => {
  return (
    <div
      className="hover:bg-neutral-300 p-2 rounded h-fit cursor-pointer"
      onClick={onClick}
    >
      {children}
    </div>
  );
};

export const AIMessage = ({
  messageId,
  content,
  query,
  citedDocuments,
  isComplete,
  hasDocs,
  handleFeedback,
  isCurrentlyShowingRetrieved,
  handleShowRetrieved,
}: {
  messageId: number | null;
  content: string | JSX.Element;
  query?: string;
  citedDocuments?: [string, DanswerDocument][] | null;
  isComplete?: boolean;
  hasDocs?: boolean;
  handleFeedback?: (feedbackType: FeedbackType) => void;
  isCurrentlyShowingRetrieved?: boolean;
  handleShowRetrieved?: (messageNumber: number | null) => void;
}) => {
  const [copyClicked, setCopyClicked] = useState(false);
  return (
    <div className={"py-5 px-5 flex -mr-6 w-full"}>
      <div className="mx-auto w-searchbar-small 3xl:w-searchbar relative">
        <div className="ml-8">
          <div className="flex">
            <div className="p-1 bg-ai rounded-lg h-fit my-auto">
              <div className="text-inverted">
                <FiCpu size={16} className="my-auto mx-auto" />
              </div>
            </div>

            <div className="font-bold text-emphasis ml-2 my-auto">Danswer</div>

            {query === undefined &&
              hasDocs &&
              handleShowRetrieved !== undefined &&
              isCurrentlyShowingRetrieved !== undefined && (
                <div className="flex w-message-small 3xl:w-message-default absolute ml-8">
                  <div className="ml-auto">
                    <ShowHideDocsButton
                      messageId={messageId}
                      isCurrentlyShowingRetrieved={isCurrentlyShowingRetrieved}
                      handleShowRetrieved={handleShowRetrieved}
                    />
                  </div>
                </div>
              )}
          </div>

          <div className="w-message-small 3xl:w-message-default break-words mt-1 ml-8">
            {query !== undefined &&
              handleShowRetrieved !== undefined &&
              isCurrentlyShowingRetrieved !== undefined && (
                <div className="my-1">
                  <SearchSummary
                    query={query}
                    hasDocs={hasDocs || false}
                    messageId={messageId}
                    isCurrentlyShowingRetrieved={isCurrentlyShowingRetrieved}
                    handleShowRetrieved={handleShowRetrieved}
                  />
                </div>
              )}

            {content ? (
              <>
                {typeof content === "string" ? (
                  <ReactMarkdown
                    className="prose max-w-full"
                    components={{
                      a: ({ node, ...props }) => (
                        <a
                          {...props}
                          className="text-blue-500 hover:text-blue-700"
                          target="_blank"
                          rel="noopener noreferrer"
                        />
                      ),
                    }}
                  >
                    {content.replaceAll("\\n", "\n")}
                  </ReactMarkdown>
                ) : (
                  content
                )}
              </>
            ) : isComplete ? (
              <div>I just performed the requested search!</div>
            ) : (
              <div className="text-sm my-auto">
                <ThreeDots
                  height="30"
                  width="50"
                  color="#3b82f6"
                  ariaLabel="grid-loading"
                  radius="12.5"
                  wrapperStyle={{}}
                  wrapperClass=""
                  visible={true}
                />
              </div>
            )}
            {citedDocuments && citedDocuments.length > 0 && (
              <div className="mt-2">
                <b className="text-sm text-emphasis">Sources:</b>
                <div className="flex flex-wrap gap-2">
                  {citedDocuments
                    .filter(([_, document]) => document.semantic_identifier)
                    .map(([citationKey, document], ind) => {
                      return (
                        <a
                          key={document.document_id}
                          href={document.link}
                          target="_blank"
                          className="text-sm border border-border py-1 px-2 rounded flex cursor-pointer hover:bg-hover"
                        >
                          <div className="max-w-350 text-ellipsis flex">
                            <div className="mr-1 my-auto">
                              <SourceIcon
                                sourceType={document.source_type}
                                iconSize={16}
                              />
                            </div>
                            [{citationKey}] {document!.semantic_identifier}
                          </div>
                        </a>
                      );
                    })}
                </div>
              </div>
            )}
          </div>
          {handleFeedback && (
            <div className="flex flex-col md:flex-row gap-x-0.5 ml-8 mt-1">
              <Hoverable
                onClick={() => {
                  navigator.clipboard.writeText(content.toString());
                  setCopyClicked(true);
                  setTimeout(() => setCopyClicked(false), 3000);
                }}
              >
                {copyClicked ? <FiCheck /> : <FiCopy />}
              </Hoverable>
              <Hoverable onClick={() => handleFeedback("like")}>
                <FiThumbsUp />
              </Hoverable>
              <Hoverable>
                <FiThumbsDown onClick={() => handleFeedback("dislike")} />
              </Hoverable>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export const HumanMessage = ({
  content,
}: {
  content: string | JSX.Element;
}) => {
  return (
    <div className="py-5 px-5 flex -mr-6 w-full">
      <div className="mx-auto w-searchbar-small 3xl:w-searchbar">
        <div className="ml-8">
          <div className="flex">
            <div className="p-1 bg-user rounded-lg h-fit">
              <div className="text-inverted">
                <FiUser size={16} className="my-auto mx-auto" />
              </div>
            </div>

            <div className="font-bold text-emphasis ml-2 my-auto">You</div>
          </div>
          <div className="mx-auto mt-1 ml-8 w-message-small 3xl:w-message-default flex flex-wrap">
            <div className="w-full sm:w-full w-message-small 3xl:w-message-default break-words">
              {typeof content === "string" ? (
                <ReactMarkdown
                  className="prose max-w-full"
                  components={{
                    a: ({ node, ...props }) => (
                      <a
                        {...props}
                        className="text-blue-500 hover:text-blue-700"
                        target="_blank"
                        rel="noopener noreferrer"
                      />
                    ),
                  }}
                >
                  {content.replaceAll("\\n", "\n")}
                </ReactMarkdown>
              ) : (
                content
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
