import {
  BookstackIcon,
  ConfluenceIcon,
  Document360Icon,
  FileIcon,
  GithubIcon,
  GlobeIcon,
  GongIcon,
  GoogleDriveIcon,
  GoogleSitesIcon,
  GuruIcon,
  HubSpotIcon,
  JiraIcon,
  LinearIcon,
  NotionIcon,
  ProductboardIcon,
  RequestTrackerIcon,
  SlabIcon,
  SlackIcon,
  ZendeskIcon,
  ZulipIcon,
} from "@/components/icons/icons";
import { ValidSources } from "./types";
import { SourceCategory, SourceMetadata } from "./search/interfaces";

interface PartialSourceMetadata {
  icon: React.FC<{ size?: number; className?: string }>;
  displayName: string;
  category: SourceCategory;
}

type SourceMap = {
  [K in ValidSources]: PartialSourceMetadata;
};

const SOURCE_METADATA_MAP: SourceMap = {
  web: {
    icon: GlobeIcon,
    displayName: "Web",
    category: SourceCategory.ImportedKnowledge,
  },
  file: {
    icon: FileIcon,
    displayName: "File",
    category: SourceCategory.ImportedKnowledge,
  },
  slack: {
    icon: SlackIcon,
    displayName: "Slack",
    category: SourceCategory.AppConnection,
  },
  google_drive: {
    icon: GoogleDriveIcon,
    displayName: "Google Drive",
    category: SourceCategory.AppConnection,
  },
  github: {
    icon: GithubIcon,
    displayName: "Github",
    category: SourceCategory.AppConnection,
  },
  confluence: {
    icon: ConfluenceIcon,
    displayName: "Confluence",
    category: SourceCategory.AppConnection,
  },
  jira: {
    icon: JiraIcon,
    displayName: "Jira",
    category: SourceCategory.AppConnection,
  },
  notion: {
    icon: NotionIcon,
    displayName: "Notion",
    category: SourceCategory.AppConnection,
  },
  zendesk: {
    icon: ZendeskIcon,
    displayName: "Zendesk",
    category: SourceCategory.AppConnection,
  },
  gong: {
    icon: GongIcon,
    displayName: "Gong",
    category: SourceCategory.AppConnection,
  },
  linear: {
    icon: LinearIcon,
    displayName: "Linear",
    category: SourceCategory.AppConnection,
  },
  productboard: {
    icon: ProductboardIcon,
    displayName: "Productboard",
    category: SourceCategory.AppConnection,
  },
  slab: {
    icon: SlabIcon,
    displayName: "Slab",
    category: SourceCategory.AppConnection,
  },
  zulip: {
    icon: ZulipIcon,
    displayName: "Zulip",
    category: SourceCategory.AppConnection,
  },
  guru: {
    icon: GuruIcon,
    displayName: "Guru",
    category: SourceCategory.AppConnection,
  },
  hubspot: {
    icon: HubSpotIcon,
    displayName: "HubSpot",
    category: SourceCategory.AppConnection,
  },
  document360: {
    icon: Document360Icon,
    displayName: "Document360",
    category: SourceCategory.AppConnection,
  },
  bookstack: {
    icon: BookstackIcon,
    displayName: "BookStack",
    category: SourceCategory.AppConnection,
  },
  google_sites: {
    icon: GoogleSitesIcon,
    displayName: "Google Sites",
    category: SourceCategory.ImportedKnowledge,
  },
  requesttracker: {
    icon: RequestTrackerIcon,
    displayName: "Request Tracker",
    category: SourceCategory.AppConnection,
  },
};

function fillSourceMetadata(
  partialMetadata: PartialSourceMetadata,
  internalName: ValidSources
): SourceMetadata {
  return {
    internalName: internalName,
    ...partialMetadata,
    adminUrl: `/admin/connectors/${partialMetadata.displayName
      .toLowerCase()
      .replaceAll(" ", "-")}`,
  };
}

export function getSourceMetadata(sourceType: ValidSources): SourceMetadata {
  return fillSourceMetadata(SOURCE_METADATA_MAP[sourceType], sourceType);
}

export function listSourceMetadata(): SourceMetadata[] {
  return Object.entries(SOURCE_METADATA_MAP).map(([source, metadata]) => {
    return fillSourceMetadata(metadata, source as ValidSources);
  });
}

export function getSourceDisplayName(sourceType: ValidSources): string | null {
  return getSourceMetadata(sourceType).displayName;
}
