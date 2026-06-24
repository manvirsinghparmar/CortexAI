import type { Parent, Root, Text } from "mdast";
import { visit } from "unist-util-visit";

const CITATION_RUN = /\[\d+\](?:\s*\[\d+\])*/g;
const CITATION_REF = /\[(\d+)\]/g;

type CitationNode = {
  type: "citation";
  data: {
    hName: "cite";
    hProperties: {
      "data-refs": string;
    };
  };
  children: [];
};

export function remarkCitations() {
  return (tree: Root) => {
    visit(tree, "text", (node: Text, index, parent: Parent | undefined) => {
      if (!parent || index === undefined || !/\[\d+\]/.test(node.value)) {
        return undefined;
      }

      const replacement = citationParts(node.value);
      if (replacement.length === 1 && replacement[0] === node) {
        return undefined;
      }

      parent.children.splice(
        index,
        1,
        ...(replacement as Array<(typeof parent.children)[number]>),
      );
      return index + replacement.length;
    });
  };
}

function citationParts(value: string): Array<Text | CitationNode> {
  const parts: Array<Text | CitationNode> = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  CITATION_RUN.lastIndex = 0;
  while ((match = CITATION_RUN.exec(value))) {
    if (match.index > lastIndex) {
      parts.push({ type: "text", value: value.slice(lastIndex, match.index) });
    }

    const refs = refsFromRun(match[0]);
    if (refs.length > 0) {
      parts.push({
        type: "citation",
        data: {
          hName: "cite",
          hProperties: {
            "data-refs": refs.join(","),
          },
        },
        children: [],
      });
    }

    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < value.length) {
    parts.push({ type: "text", value: value.slice(lastIndex) });
  }

  return parts.length > 0 ? parts : [{ type: "text", value }];
}

function refsFromRun(value: string): number[] {
  const refs: number[] = [];
  let match: RegExpExecArray | null;

  CITATION_REF.lastIndex = 0;
  while ((match = CITATION_REF.exec(value))) {
    refs.push(Number(match[1]));
  }

  return refs;
}
