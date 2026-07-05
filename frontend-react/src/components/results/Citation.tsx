import type { CSSProperties, MouseEventHandler } from "react";
import {
  forwardRef,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import type { WebSourceItem } from "../../types";
import { faviconUrl, publisherName } from "../../utils/sourceMeta";
import { CortexIcon } from "../shared/CortexIcon";
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
  onMouseEnter?: MouseEventHandler<HTMLSpanElement>;
  onMouseLeave?: MouseEventHandler<HTMLSpanElement>;
}

export function Citation({ refs, sources }: CitationProps) {
  const citationId = useId();
  const rootRef = useRef<HTMLSpanElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLSpanElement>(null);
  const closeTimerRef = useRef<number | null>(null);
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
    return () => {
      if (closeTimerRef.current !== null) {
        window.clearTimeout(closeTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!open) return undefined;

    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (
        !rootRef.current?.contains(target) &&
        !dialogRef.current?.contains(target)
      ) {
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

  useLayoutEffect(() => {
    if (!open || smallScreen) return undefined;

    const updatePosition = () => {
      const preview = dialogRef.current;
      const previewHeight = preview
        ? Math.max(preview.scrollHeight, preview.getBoundingClientRect().height)
        : undefined;
      setPosition(
        resolvePopoverPosition(
          buttonRef.current?.getBoundingClientRect(),
          previewHeight,
        ),
      );
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
    if (open && smallScreen) {
      window.setTimeout(() => dialogRef.current?.focus(), 0);
    }
  }, [open, smallScreen]);

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
  const firstSourceHref = externalSourceHref(citedSources[0].url);

  const clearCloseTimer = () => {
    if (closeTimerRef.current !== null) {
      window.clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
  };

  const openPreview = () => {
    clearCloseTimer();
    window.dispatchEvent(new CustomEvent(CITATION_OPEN_EVENT, { detail: citationId }));
    setOpen(true);
  };

  const scheduleDesktopClose = () => {
    if (smallScreen) return;
    clearCloseTimer();
    closeTimerRef.current = window.setTimeout(() => {
      setOpen(false);
      closeTimerRef.current = null;
    }, 90);
  };

  const toggleOpen = () => {
    if (!smallScreen) return;
    setOpen((current) => {
      const next = !current;
      if (next) {
        window.dispatchEvent(new CustomEvent(CITATION_OPEN_EVENT, { detail: citationId }));
      }
      return next;
    });
  };

  const handleDesktopMouseEnter: MouseEventHandler<HTMLSpanElement> = () => {
    if (!smallScreen) openPreview();
  };

  const handleDesktopMouseLeave: MouseEventHandler<HTMLSpanElement> = () => {
    scheduleDesktopClose();
  };

  const preview = open ? (
    smallScreen ? (
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
        onMouseEnter={clearCloseTimer}
        onMouseLeave={scheduleDesktopClose}
      />
    )
  ) : null;

  return (
    <span
      ref={rootRef}
      className={`${styles.citationRoot} ${open ? styles.citationRootOpen : ""}`}
      onMouseEnter={handleDesktopMouseEnter}
      onMouseLeave={handleDesktopMouseLeave}
    >
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
      </button>
      <a
        className={styles.citationExternalLink}
        href={firstSourceHref}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={`Open ${firstPublisher} source in a new tab`}
        title={`Open ${firstPublisher}`}
      >
        <CortexIcon
          name="external-link"
          className={styles.citationExternalIcon}
          size={13}
          strokeWidth={2.2}
        />
      </a>
      {preview && typeof document !== "undefined"
        ? createPortal(preview, document.body)
        : null}
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
    onMouseEnter,
    onMouseLeave,
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
    onMouseEnter={onMouseEnter}
    onMouseLeave={onMouseLeave}
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
            href={externalSourceHref(source.url)}
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

function externalSourceHref(url: string): string {
  const trimmed = url.trim();
  if (!trimmed) return "#";
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  if (trimmed.startsWith("//")) return `https:${trimmed}`;
  return `https://${trimmed.replace(/^\/+/, "")}`;
}

function resolvePopoverPosition(
  rect: DOMRect | undefined,
  previewHeight: number | undefined,
): PopoverPosition {
  const margin = 12;
  const gap = 8;
  const maxPreviewHeight = 360;
  const width = Math.min(360, window.innerWidth - margin * 2);

  if (!rect) {
    return {
      left: margin,
      top: margin,
      maxHeight: Math.max(160, window.innerHeight - margin * 2),
    };
  }

  const left = clamp(rect.left, margin, window.innerWidth - width - margin);
  const belowHeight = Math.max(0, window.innerHeight - rect.bottom - margin - gap);
  const aboveHeight = Math.max(0, rect.top - margin - gap);
  const desiredHeight = Math.min(
    maxPreviewHeight,
    previewHeight && previewHeight > 0 ? previewHeight : maxPreviewHeight,
  );

  if (belowHeight < desiredHeight && aboveHeight >= belowHeight) {
    const maxHeight = Math.max(1, Math.min(maxPreviewHeight, aboveHeight));
    const renderedHeight = Math.min(desiredHeight, maxHeight);
    return {
      left,
      top: Math.max(margin, rect.top - renderedHeight - gap),
      maxHeight,
    };
  }

  const top = rect.bottom + gap;
  return {
    left,
    top,
    maxHeight: Math.max(1, Math.min(maxPreviewHeight, belowHeight)),
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
