import type { CSSProperties, MouseEventHandler } from "react";
import { forwardRef, useEffect, useId, useMemo, useRef, useState } from "react";
import type { WebSourceItem } from "../../types";
import { faviconUrl, publisherName } from "../../utils/sourceMeta";
import styles from "./ResponseCard.module.css";

interface CitationProps {
  refs: string;
  sources: WebSourceItem[];
}

interface PopoverPosition {
  left: number;
  top: number;
  maxHeight: number;
}

type PopoverStyle = CSSProperties & {
  "--citation-popover-left": string;
  "--citation-popover-top": string;
  "--citation-popover-max-height": string;
};

const CITATION_OPEN_EVENT = "cortex-citation-open";
const SMALL_SCREEN_QUERY = "(max-width: 760px)";

interface CitationPreviewProps {
  id: string;
  sources: WebSourceItem[];
  failedFavicons: Set<string>;
  onFaviconError: (url: string) => void;
  className: string;
  style?: CSSProperties;
  onClick?: MouseEventHandler<HTMLSpanElement>;
}

export function Citation({ refs, sources }: CitationProps) {
  const citationId = useId();
  const rootRef = useRef<HTMLSpanElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLSpanElement>(null);
  const [open, setOpen] = useState(false);
  const [failedFavicons, setFailedFavicons] = useState<Set<string>>(() => new Set());
  const [position, setPosition] = useState<PopoverPosition>(() => ({
    left: 12,
    top: 12,
    maxHeight: 360,
  }));
  const smallScreen = useMediaQuery(SMALL_SCREEN_QUERY);
  const citedSources = useMemo(() => resolveCitedSources(refs, sources), [refs, sources]);

  useEffect(() => {
    if (!open) return undefined;

    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
        buttonRef.current?.focus();
      }
    };

    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  useEffect(() => {
    const onOpen = (event: Event) => {
      const detail = (event as CustomEvent<string>).detail;
      if (detail !== citationId) {
        setOpen(false);
      }
    };

    window.addEventListener(CITATION_OPEN_EVENT, onOpen);
    return () => window.removeEventListener(CITATION_OPEN_EVENT, onOpen);
  }, [citationId]);

  useEffect(() => {
    if (!open || smallScreen) return undefined;

    const updatePosition = () => {
      setPosition(resolvePopoverPosition(buttonRef.current?.getBoundingClientRect()));
    };

    updatePosition();
    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);
    return () => {
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
    };
  }, [open, smallScreen]);

  useEffect(() => {
    if (open) {
      window.setTimeout(() => dialogRef.current?.focus(), 0);
    }
  }, [open]);

  if (citedSources.length === 0) {
    return null;
  }

  const firstPublisher = publisherName(citedSources[0]);
  const extraCount = citedSources.length - 1;
  const label = extraCount > 0 ? `${firstPublisher} + ${extraCount}` : firstPublisher;
  const ariaLabel =
    extraCount > 0
      ? `Sources: ${firstPublisher} and ${extraCount} more`
      : `Source: ${firstPublisher}`;
  const previewId = `${citationId}-preview`;

  const toggleOpen = () => {
    setOpen((current) => {
      const next = !current;
      if (next) {
        window.dispatchEvent(new CustomEvent(CITATION_OPEN_EVENT, { detail: citationId }));
      }
      return next;
    });
  };

  return (
    <span ref={rootRef} className={styles.citationRoot}>
      <button
        ref={buttonRef}
        type="button"
        className={styles.citationButton}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={previewId}
        aria-label={ariaLabel}
        onClick={toggleOpen}
      >
        <span className={styles.citationLabel}>{label}</span>
        <ExternalLinkIcon />
      </button>
      {open &&
        (smallScreen ? (
          <span
            className={styles.citationSheetBackdrop}
            onClick={() => setOpen(false)}
          >
            <CitationPreview
              id={previewId}
              ref={dialogRef}
              sources={citedSources}
              failedFavicons={failedFavicons}
              onFaviconError={(url) => {
                setFailedFavicons((current) => new Set(current).add(url));
              }}
              className={`${styles.citationPreview} ${styles.citationSheet}`}
              onClick={(event) => event.stopPropagation()}
            />
          </span>
        ) : (
          <CitationPreview
            id={previewId}
            ref={dialogRef}
            sources={citedSources}
            failedFavicons={failedFavicons}
            onFaviconError={(url) => {
              setFailedFavicons((current) => new Set(current).add(url));
            }}
            className={`${styles.citationPreview} ${styles.citationPopover}`}
            style={popoverStyle(position)}
          />
        ))}
    </span>
  );
}

const CitationPreview = forwardRef<HTMLSpanElement, CitationPreviewProps>(function CitationPreview(
  {
    id,
    sources,
    failedFavicons,
    onFaviconError,
    className,
    style,
    onClick,
  },
  ref,
) {
  return (
  <span
    id={id}
    ref={ref}
    role="dialog"
    aria-label="Citation sources"
    tabIndex={-1}
    className={className}
    style={style}
    onClick={onClick}
  >
    <span className={styles.citationPreviewTitle}>Sources</span>
    <span className={styles.citationSourceList}>
      {sources.map((source, index) => {
        const publisher = publisherName(source);
        const iconUrl = faviconUrl(source);
        const iconFailed = failedFavicons.has(source.url);
        return (
          <a
            key={`${source.url}-${index}`}
            className={styles.citationSourceLink}
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
          >
            <span className={styles.citationIconSlot} aria-hidden="true">
              {iconFailed ? (
                <span className={styles.citationIconFallback}>
                  {publisher.charAt(0).toUpperCase() || "S"}
                </span>
              ) : (
                <img
                  className={styles.citationFavicon}
                  src={iconUrl}
                  alt=""
                  loading="lazy"
                  onError={() => onFaviconError(source.url)}
                />
              )}
            </span>
            <span className={styles.citationSourceText}>
              <span className={styles.citationSourceTitle}>{source.title || source.url}</span>
              <span className={styles.citationSourcePublisher}>{publisher}</span>
            </span>
          </a>
        );
      })}
    </span>
  </span>
  );
});

function resolveCitedSources(refs: string, sources: WebSourceItem[]): WebSourceItem[] {
  return refs
    .split(",")
    .map((ref) => Number(ref.trim()))
    .filter((ref) => Number.isInteger(ref) && ref > 0)
    .map((ref) => sources[ref - 1])
    .filter((source): source is WebSourceItem => !!source);
}

function resolvePopoverPosition(rect: DOMRect | undefined): PopoverPosition {
  const margin = 12;
  const gap = 8;
  const width = Math.min(360, window.innerWidth - margin * 2);

  if (!rect) {
    return {
      left: margin,
      top: margin,
      maxHeight: Math.max(160, window.innerHeight - margin * 2),
    };
  }

  const left = clamp(rect.left, margin, window.innerWidth - width - margin);
  const belowHeight = window.innerHeight - rect.bottom - margin - gap;
  const aboveHeight = rect.top - margin - gap;

  if (belowHeight < 220 && aboveHeight > belowHeight) {
    const preferredHeight = Math.min(360, aboveHeight);
    const top = Math.max(margin, rect.top - preferredHeight - gap);
    return {
      left,
      top,
      maxHeight: Math.max(160, rect.top - top - gap),
    };
  }

  const top = rect.bottom + gap;
  return {
    left,
    top,
    maxHeight: Math.max(160, window.innerHeight - top - margin),
  };
}

function popoverStyle(position: PopoverPosition): PopoverStyle {
  return {
    "--citation-popover-left": `${position.left}px`,
    "--citation-popover-top": `${position.top}px`,
    "--citation-popover-max-height": `${position.maxHeight}px`,
  };
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), Math.max(min, max));
}

function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches);

  useEffect(() => {
    const media = window.matchMedia(query);
    const onChange = () => setMatches(media.matches);

    setMatches(media.matches);
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [query]);

  return matches;
}

function ExternalLinkIcon() {
  return (
    <svg className={styles.citationExternalIcon} viewBox="0 0 16 16" aria-hidden="true">
      <path d="M6 4h6v6" />
      <path d="m5 11 7-7" />
      <path d="M12 12H4V4h3" />
    </svg>
  );
}
