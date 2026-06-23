import { render, screen, cleanup, act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

vi.mock("motion/react", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
    button: ({ children, ...props }: any) => (
      <button {...props}>{children}</button>
    ),
  },
  AnimatePresence: ({ children }: any) => <div>{children}</div>,
}));

vi.mock("lucide-react", () => ({
  Folder: () => <svg data-testid="folder-icon" />,
  FileText: () => <svg data-testid="file-icon" />,
  Search: () => <svg data-testid="search-icon" />,
  Globe: () => <svg data-testid="globe-icon" />,
  Check: () => <svg data-testid="check-icon" />,
  Sparkles: () => <svg data-testid="sparkles-icon" />,
  Terminal: () => <svg data-testid="terminal-icon" />,
  Play: () => <svg data-testid="play-icon" />,
  Pause: () => <svg data-testid="pause-icon" />,
}));

vi.mock("@/components/workspace/tooltip", () => ({
  Tooltip: ({ children, content }: any) => (
    <div>
      {content && <span className="sr-only">{content}</span>}
      {children}
    </div>
  ),
}));

import ProgressiveSkillsAnimation from "@/components/landing/progressive-skills-animation";

// Polyfill scrollTo for jsdom (used by chatMessagesRef)
if (!HTMLElement.prototype.scrollTo) {
  HTMLElement.prototype.scrollTo = vi.fn();
}

const originalIntersectionObserver = globalThis.IntersectionObserver;

/**
 * Helper: click the overlay play button and advance timers past the
 * initial "user-input" phase (delay 0) so phase-dependent content renders.
 */
function clickOverlayPlayAndStart() {
  const elements = screen.getAllByText("Click to play");
  const overlayButton = elements[0]!.closest("button")!;
  act(() => {
    overlayButton.click();
  });
  act(() => {
    vi.advanceTimersByTime(1);
  });
}

/** Get the bottom play/pause button */
function getPlayPauseToggleButton() {
  const srOnly = screen.getByText("Play / Pause");
  const tooltipDiv = srOnly.parentElement!;
  return tooltipDiv.querySelector("button") as HTMLElement;
}

class MockIntersectionObserver {
  _callback: IntersectionObserverCallback;
  _options?: IntersectionObserverInit;
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
  root = null;
  rootMargin = "";
  thresholds = [0];

  constructor(
    callback: IntersectionObserverCallback,
    options?: IntersectionObserverInit,
  ) {
    this._callback = callback;
    this._options = options;
  }

  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }
}

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  globalThis.IntersectionObserver = originalIntersectionObserver;
});

describe("ProgressiveSkillsAnimation", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  describe("initial render (idle state)", () => {
    test("renders the component with play overlay", () => {
      render(<ProgressiveSkillsAnimation />);
      expect(
        screen.getAllByText("Click to play").length,
      ).toBeGreaterThanOrEqual(1);
    });

    test("renders file tree root folders", () => {
      render(<ProgressiveSkillsAnimation />);
      expect(screen.getByText("deep-search")).toBeInTheDocument();
      expect(screen.getByText("frontend-design")).toBeInTheDocument();
      expect(screen.getByText("deploy")).toBeInTheDocument();
    });

    test("renders file tree sub-files", () => {
      render(<ProgressiveSkillsAnimation />);
      const skillFiles = screen.getAllByText("SKILL.md");
      expect(skillFiles.length).toBe(3);
      expect(screen.getByText("biotech.md")).toBeInTheDocument();
      expect(screen.getByText("computer-science.md")).toBeInTheDocument();
      expect(screen.getByText("physics.md")).toBeInTheDocument();
      expect(screen.getByText("scripts")).toBeInTheDocument();
      expect(screen.getByText("deploy.sh")).toBeInTheDocument();
    });

    test("renders chat interface header", () => {
      render(<ProgressiveSkillsAnimation />);
      expect(screen.getByText("iDeer Agent")).toBeInTheDocument();
    });

    test("renders chat input placeholder", () => {
      render(<ProgressiveSkillsAnimation />);
      expect(screen.getByText("Ask iDeer anything...")).toBeInTheDocument();
    });

    test("renders play/pause tooltip", () => {
      render(<ProgressiveSkillsAnimation />);
      expect(screen.getByText("Play / Pause")).toBeInTheDocument();
    });

    test("renders path prefix", () => {
      render(<ProgressiveSkillsAnimation />);
      expect(screen.getByText("/mnt/skills/")).toBeInTheDocument();
    });

    test("does not show user message in idle state", () => {
      render(<ProgressiveSkillsAnimation />);
      expect(
        screen.queryByText(/Research mRNA delivery/),
      ).not.toBeInTheDocument();
    });

    test("does not show agent messages in idle state", () => {
      render(<ProgressiveSkillsAnimation />);
      expect(screen.queryByText(/Found 3 skills/)).not.toBeInTheDocument();
    });
  });

  describe("handlePlay - starts animation", () => {
    test("hides overlay after play button is clicked", () => {
      render(<ProgressiveSkillsAnimation />);
      const overlayButton = screen
        .getAllByText("Click to play")[0]!
        .closest("button")!;
      act(() => {
        overlayButton.click();
      });
      expect(screen.queryAllByText("Click to play").length).toBe(0);
    });

    test("shows user message after play is clicked", () => {
      render(<ProgressiveSkillsAnimation />);
      clickOverlayPlayAndStart();
      expect(screen.getByText(/Research mRNA delivery/)).toBeInTheDocument();
    });

    test("transitions through all phases with timers", () => {
      render(<ProgressiveSkillsAnimation />);
      clickOverlayPlayAndStart();

      // user-input phase
      expect(screen.getByText(/Research mRNA delivery/)).toBeInTheDocument();

      // Advance past scanning
      act(() => {
        vi.advanceTimersByTime(1999);
      });
      expect(screen.getByText(/Found 3 skills/)).toBeInTheDocument();

      // Advance past load-skill
      act(() => {
        vi.advanceTimersByTime(1500);
      });
      expect(
        screen.getByText("Loading deep-search/SKILL.md..."),
      ).toBeInTheDocument();

      // Advance past load-template
      act(() => {
        vi.advanceTimersByTime(1200);
      });
      expect(
        screen.getByText(
          "Found biotech related topic, loading deep-search/biotech.md...",
        ),
      ).toBeInTheDocument();

      // Advance past researching
      act(() => {
        vi.advanceTimersByTime(800);
      });
      expect(screen.getByText(/Researching/)).toBeInTheDocument();

      // Advance past load-frontend (to build phase where frontend SKILL.md appears)
      act(() => {
        vi.advanceTimersByTime(800 + 1200);
      });
      expect(screen.getByText(/Building/)).toBeInTheDocument();
      expect(
        screen.getByText("Loading frontend-design/SKILL.md..."),
      ).toBeInTheDocument();
      expect(screen.getByText(/Building/)).toBeInTheDocument();

      // Advance past load-deploy
      act(() => {
        vi.advanceTimersByTime(2500);
      });
      expect(screen.getByText(/Deploying/)).toBeInTheDocument();
      expect(
        screen.getByText("Loading deploy/SKILL.md..."),
      ).toBeInTheDocument();

      // Advance past deploying
      act(() => {
        vi.advanceTimersByTime(1200);
      });
      expect(
        screen.getByText("Executing scripts/deploy.sh"),
      ).toBeInTheDocument();

      // Advance past done
      act(() => {
        vi.advanceTimersByTime(2500);
      });
      expect(
        screen.getByText(/Live at biotech-startup\.vercel\.app/),
      ).toBeInTheDocument();
    });
  });

  describe("handleTogglePlayPause", () => {
    test("pauses animation when playing", () => {
      render(<ProgressiveSkillsAnimation />);
      clickOverlayPlayAndStart();

      const pauseBtn = getPlayPauseToggleButton();
      act(() => {
        pauseBtn.click();
      });

      expect(
        screen.getAllByText("Click to play").length,
      ).toBeGreaterThanOrEqual(1);
    });

    test("resumes animation when paused at non-idle phase", () => {
      render(<ProgressiveSkillsAnimation />);
      clickOverlayPlayAndStart();

      // Advance to scanning
      act(() => {
        vi.advanceTimersByTime(1999);
      });
      expect(screen.getByText(/Found 3 skills/)).toBeInTheDocument();

      // Pause
      const pauseBtn = getPlayPauseToggleButton();
      act(() => {
        pauseBtn.click();
      });

      // Resume via toggle button (handleTogglePlayPause when phase !== idle)
      const resumeBtn = getPlayPauseToggleButton();
      act(() => {
        resumeBtn.click();
      });

      // After resuming, isPlaying=true, toggle shows "Play / Pause"
      expect(screen.getByText("Play / Pause")).toBeInTheDocument();

      // Resume creates new timeouts from beginning; advance to load-skill (3500ms)
      act(() => {
        vi.advanceTimersByTime(1);
      }); // user-input at 0ms
      act(() => {
        vi.advanceTimersByTime(1999);
      }); // scanning at 2000ms
      act(() => {
        vi.advanceTimersByTime(1500);
      }); // load-skill at 3500ms
      expect(
        screen.getByText("Loading deep-search/SKILL.md..."),
      ).toBeInTheDocument();
    });

    test("restarts from beginning when toggling from idle phase", () => {
      render(<ProgressiveSkillsAnimation />);
      clickOverlayPlayAndStart();

      // Pause it
      const pauseBtn = getPlayPauseToggleButton();
      act(() => {
        pauseBtn.click();
      });

      // After pausing, isPlaying=false, hasPlayed=true
      // Overlay is hidden, toggle shows "Click to play"
      // Click toggle to restart (handleTogglePlayPause when phase !== idle)
      const restartBtn = getPlayPauseToggleButton();
      act(() => {
        restartBtn.click();
      });

      expect(screen.getByText("Play / Pause")).toBeInTheDocument();
    });
  });

  describe("auto-play via IntersectionObserver", () => {
    test("auto-plays when container enters viewport", () => {
      const observerInstances: InstanceType<typeof MockIntersectionObserver>[] =
        [];
      const OriginalIO = globalThis.IntersectionObserver;

      globalThis.IntersectionObserver = class extends MockIntersectionObserver {
        constructor(
          cb: IntersectionObserverCallback,
          opts?: IntersectionObserverInit,
        ) {
          super(cb, opts);
          observerInstances.push(this);
        }
      } as unknown as typeof IntersectionObserver;

      render(<ProgressiveSkillsAnimation />);

      act(() => {
        observerInstances[0]!._callback(
          [{ isIntersecting: true } as IntersectionObserverEntry],
          {} as IntersectionObserver,
        );
      });

      act(() => {
        vi.advanceTimersByTime(300);
      });

      // The 300ms timeout fires isPlaying=true, which triggers useEffect
      // creating new timeouts. Advance 1ms to fire the user-input phase.
      act(() => {
        vi.advanceTimersByTime(1);
      });

      expect(screen.queryAllByText("Click to play").length).toBe(0);
      expect(screen.getByText(/Research mRNA delivery/)).toBeInTheDocument();

      globalThis.IntersectionObserver = OriginalIO;
    });

    test("does not auto-play when not intersecting", () => {
      const observerInstances: InstanceType<typeof MockIntersectionObserver>[] =
        [];
      const OriginalIO = globalThis.IntersectionObserver;

      globalThis.IntersectionObserver = class extends MockIntersectionObserver {
        constructor(
          cb: IntersectionObserverCallback,
          opts?: IntersectionObserverInit,
        ) {
          super(cb, opts);
          observerInstances.push(this);
        }
      } as unknown as typeof IntersectionObserver;

      render(<ProgressiveSkillsAnimation />);

      act(() => {
        observerInstances[0]!._callback(
          [{ isIntersecting: false } as IntersectionObserverEntry],
          {} as IntersectionObserver,
        );
      });

      act(() => {
        vi.advanceTimersByTime(500);
      });

      expect(
        screen.getAllByText("Click to play").length,
      ).toBeGreaterThanOrEqual(1);

      globalThis.IntersectionObserver = OriginalIO;
    });

    test("only auto-plays once", () => {
      const observerInstances: InstanceType<typeof MockIntersectionObserver>[] =
        [];
      const OriginalIO = globalThis.IntersectionObserver;

      globalThis.IntersectionObserver = class extends MockIntersectionObserver {
        constructor(
          cb: IntersectionObserverCallback,
          opts?: IntersectionObserverInit,
        ) {
          super(cb, opts);
          observerInstances.push(this);
        }
      } as unknown as typeof IntersectionObserver;

      render(<ProgressiveSkillsAnimation />);

      act(() => {
        observerInstances[0]!._callback(
          [{ isIntersecting: true } as IntersectionObserverEntry],
          {} as IntersectionObserver,
        );
      });

      act(() => {
        vi.advanceTimersByTime(300);
      });

      // Advance 1ms more to fire the user-input phase timeout
      act(() => {
        vi.advanceTimersByTime(1);
      });

      expect(screen.getByText(/Research mRNA delivery/)).toBeInTheDocument();

      const pauseBtn = getPlayPauseToggleButton();
      act(() => {
        pauseBtn.click();
      });

      expect(observerInstances[0]!.observe).toHaveBeenCalledTimes(1);

      globalThis.IntersectionObserver = OriginalIO;
    });

    test("cleans up observer on unmount", () => {
      const observerInstances: InstanceType<typeof MockIntersectionObserver>[] =
        [];
      const OriginalIO = globalThis.IntersectionObserver;

      globalThis.IntersectionObserver = class extends MockIntersectionObserver {
        constructor(
          cb: IntersectionObserverCallback,
          opts?: IntersectionObserverInit,
        ) {
          super(cb, opts);
          observerInstances.push(this);
        }
      } as unknown as typeof IntersectionObserver;

      const { unmount } = render(<ProgressiveSkillsAnimation />);
      unmount();

      expect(observerInstances[0]!.unobserve).toHaveBeenCalled();

      globalThis.IntersectionObserver = OriginalIO;
    });
  });

  describe("search animation effect (researching phase)", () => {
    test("shows search steps during researching phase", () => {
      render(<ProgressiveSkillsAnimation />);
      clickOverlayPlayAndStart();

      act(() => {
        vi.advanceTimersByTime(1999 + 1500 + 1200 + 800);
      });
      expect(screen.getByText(/Researching/)).toBeInTheDocument();

      act(() => {
        vi.advanceTimersByTime(350);
      });
      expect(
        screen.getByText("mRNA lipid nanoparticle delivery 2024"),
      ).toBeInTheDocument();
    });

    test("shows multiple search steps as time progresses", () => {
      render(<ProgressiveSkillsAnimation />);
      clickOverlayPlayAndStart();

      act(() => {
        vi.advanceTimersByTime(1999 + 1500 + 1200 + 800);
      });

      act(() => {
        vi.advanceTimersByTime(350);
      });
      expect(
        screen.getByText("mRNA lipid nanoparticle delivery 2024"),
      ).toBeInTheDocument();

      act(() => {
        vi.advanceTimersByTime(350);
      });
      expect(
        screen.getByText("nature.com/articles/s41587-024..."),
      ).toBeInTheDocument();

      act(() => {
        vi.advanceTimersByTime(350);
      });
      expect(
        screen.getByText("LNP ionizable lipids efficiency"),
      ).toBeInTheDocument();

      act(() => {
        vi.advanceTimersByTime(350);
      });
      expect(
        screen.getByText("pubs.acs.org/doi/10.1021/..."),
      ).toBeInTheDocument();

      act(() => {
        vi.advanceTimersByTime(350);
      });
      expect(
        screen.getByText("targeted mRNA tissue-specific"),
      ).toBeInTheDocument();
    });
  });

  describe("build animation effect (building phase)", () => {
    test("shows workspace files being generated during building phase", () => {
      render(<ProgressiveSkillsAnimation />);
      clickOverlayPlayAndStart();

      act(() => {
        vi.advanceTimersByTime(1999 + 1500 + 1200 + 800 + 800 + 1200);
      });
      expect(screen.getByText(/Building/)).toBeInTheDocument();

      act(() => {
        vi.advanceTimersByTime(600);
      });
      expect(screen.getByText("Generating index.html...")).toBeInTheDocument();

      act(() => {
        vi.advanceTimersByTime(600);
      });
      expect(screen.getByText("Generating index.css...")).toBeInTheDocument();

      act(() => {
        vi.advanceTimersByTime(600);
      });
      expect(screen.getByText("Generating index.js...")).toBeInTheDocument();
    });
  });

  describe("getFileTree - file tree rendering by phase", () => {
    test("file tree items have correct classes in idle phase", () => {
      render(<ProgressiveSkillsAnimation />);
      const deepSearch = screen.getByText("deep-search").closest(".flex")!;
      expect(deepSearch.className).toContain("text-zinc-600");
    });

    test("file tree highlights during scanning phase", () => {
      render(<ProgressiveSkillsAnimation />);
      clickOverlayPlayAndStart();
      act(() => {
        vi.advanceTimersByTime(1999);
      });

      const deepSearch = screen.getByText("deep-search").closest(".flex")!;
      expect(deepSearch.className).toContain("text-purple-400");
    });

    test("file tree shows dragging state for load-skill phase", () => {
      render(<ProgressiveSkillsAnimation />);
      clickOverlayPlayAndStart();
      act(() => {
        vi.advanceTimersByTime(1999 + 1500);
      });

      const skillFiles = screen.getAllByText("SKILL.md");
      const draggingSkill = skillFiles[0]!.closest(".flex")!;
      expect(draggingSkill.className).toContain("text-blue-400");
      expect(draggingSkill.className).toContain("translate-x-8");
    });

    test("file tree shows active state for load-template phase", () => {
      render(<ProgressiveSkillsAnimation />);
      clickOverlayPlayAndStart();
      act(() => {
        vi.advanceTimersByTime(1999 + 1500 + 1200);
      });

      const deepSearch = screen.getByText("deep-search").closest(".flex")!;
      expect(deepSearch.className).toContain("text-white");
    });

    test("file tree shows done state after researching", () => {
      render(<ProgressiveSkillsAnimation />);
      clickOverlayPlayAndStart();
      act(() => {
        vi.advanceTimersByTime(1999 + 1500 + 1200 + 800);
      });

      const deepSearch = screen.getByText("deep-search").closest(".flex")!;
      expect(deepSearch.className).toContain("text-green-500");

      const biotech = screen.getByText("biotech.md").closest(".flex")!;
      expect(biotech.className).toContain("text-green-500");
    });

    test("file tree shows done checkmarks for completed items", () => {
      render(<ProgressiveSkillsAnimation />);
      clickOverlayPlayAndStart();
      act(() => {
        vi.advanceTimersByTime(1999 + 1500 + 1200);
      });

      const checkIcons = screen.getAllByTestId("check-icon");
      expect(checkIcons.length).toBeGreaterThan(0);
    });

    test("file tree shows sparkles for highlighted items", () => {
      render(<ProgressiveSkillsAnimation />);
      clickOverlayPlayAndStart();
      act(() => {
        vi.advanceTimersByTime(1999);
      });

      const sparklesIcons = screen.getAllByTestId("sparkles-icon");
      expect(sparklesIcons.length).toBeGreaterThan(0);
    });

    test("frontend-design folder shows correct states", () => {
      render(<ProgressiveSkillsAnimation />);
      clickOverlayPlayAndStart();
      // Advance to load-frontend (6300ms total)
      act(() => {
        vi.advanceTimersByTime(1999 + 1500 + 1200 + 800 + 800);
      });

      const frontendFolder = screen
        .getByText("frontend-design")
        .closest(".flex")!;
      expect(frontendFolder.className).toContain("text-white");

      // Advance to building (7500ms total) where frontend-design is done
      act(() => {
        vi.advanceTimersByTime(1200);
      });

      const frontendFolderDone = screen
        .getByText("frontend-design")
        .closest(".flex")!;
      expect(frontendFolderDone.className).toContain("text-green-500");
    });

    test("deploy folder shows correct states", () => {
      render(<ProgressiveSkillsAnimation />);
      clickOverlayPlayAndStart();
      act(() => {
        vi.advanceTimersByTime(1999 + 1500 + 1200 + 800 + 800 + 1200 + 2500);
      });

      const deployFolder = screen.getByText("deploy").closest(".flex")!;
      expect(deployFolder.className).toContain("text-white");

      act(() => {
        vi.advanceTimersByTime(1200);
      });

      const deployFolderDone = screen.getByText("deploy").closest(".flex")!;
      expect(deployFolderDone.className).toContain("text-green-500");
    });

    test("scripts folder shows done state during deploying", () => {
      render(<ProgressiveSkillsAnimation />);
      clickOverlayPlayAndStart();
      act(() => {
        vi.advanceTimersByTime(
          1999 + 1500 + 1200 + 800 + 800 + 1200 + 2500 + 1200,
        );
      });

      const scriptsFolder = screen.getByText("scripts").closest(".flex")!;
      expect(scriptsFolder.className).toContain("text-green-500");

      const deploySh = screen.getByText("deploy.sh").closest(".flex")!;
      expect(deploySh.className).toContain("text-green-500");
    });
  });

  describe("chat messages rendering", () => {
    test("shows user message for all non-idle phases", () => {
      render(<ProgressiveSkillsAnimation />);
      clickOverlayPlayAndStart();

      expect(screen.getByText(/Research mRNA delivery/)).toBeInTheDocument();

      act(() => {
        vi.advanceTimersByTime(1999);
      });
      expect(screen.getByText(/Research mRNA delivery/)).toBeInTheDocument();
    });

    test("shows Found 3 skills message during scanning phase", () => {
      render(<ProgressiveSkillsAnimation />);
      clickOverlayPlayAndStart();
      act(() => {
        vi.advanceTimersByTime(1999);
      });
      expect(screen.getByText(/Found 3 skills/)).toBeInTheDocument();
    });

    test("shows researching section during load-skill phase", () => {
      render(<ProgressiveSkillsAnimation />);
      clickOverlayPlayAndStart();
      act(() => {
        vi.advanceTimersByTime(1999 + 1500);
      });

      expect(screen.getByText(/Researching/)).toBeInTheDocument();
      expect(
        screen.getByText("Loading deep-search/SKILL.md..."),
      ).toBeInTheDocument();
    });

    test("shows building section during building phase", () => {
      render(<ProgressiveSkillsAnimation />);
      clickOverlayPlayAndStart();
      act(() => {
        vi.advanceTimersByTime(1999 + 1500 + 1200 + 800 + 800 + 1200);
      });

      expect(screen.getByText(/Building/)).toBeInTheDocument();
      expect(
        screen.getByText("Loading frontend-design/SKILL.md..."),
      ).toBeInTheDocument();
    });

    test("shows deploying section during load-deploy phase", () => {
      render(<ProgressiveSkillsAnimation />);
      clickOverlayPlayAndStart();
      act(() => {
        vi.advanceTimersByTime(1999 + 1500 + 1200 + 800 + 800 + 1200 + 2500);
      });

      expect(screen.getByText(/Deploying/)).toBeInTheDocument();
      expect(
        screen.getByText("Loading deploy/SKILL.md..."),
      ).toBeInTheDocument();
    });

    test("shows deploy script execution during deploying phase", () => {
      render(<ProgressiveSkillsAnimation />);
      clickOverlayPlayAndStart();
      act(() => {
        vi.advanceTimersByTime(
          1999 + 1500 + 1200 + 800 + 800 + 1200 + 2500 + 1200,
        );
      });

      expect(
        screen.getByText("Executing scripts/deploy.sh"),
      ).toBeInTheDocument();
    });

    test("shows live URL in done phase", () => {
      render(<ProgressiveSkillsAnimation />);
      clickOverlayPlayAndStart();
      act(() => {
        vi.advanceTimersByTime(
          1999 + 1500 + 1200 + 800 + 800 + 1200 + 2500 + 1200 + 2500,
        );
      });

      expect(
        screen.getByText(/Live at biotech-startup\.vercel\.app/),
      ).toBeInTheDocument();
    });
  });

  describe("animation reset after completion", () => {
    test("resets to idle after final display duration", () => {
      render(<ProgressiveSkillsAnimation />);
      clickOverlayPlayAndStart();

      act(() => {
        vi.advanceTimersByTime(16700);
      });

      expect(
        screen.getAllByText("Click to play").length,
      ).toBeGreaterThanOrEqual(1);
    });
  });

  describe("icon rendering", () => {
    test("renders folder icons for folder items", () => {
      render(<ProgressiveSkillsAnimation />);
      const folderIcons = screen.getAllByTestId("folder-icon");
      expect(folderIcons.length).toBeGreaterThan(0);
    });

    test("renders file icons for file items", () => {
      render(<ProgressiveSkillsAnimation />);
      const fileIcons = screen.getAllByTestId("file-icon");
      expect(fileIcons.length).toBeGreaterThan(0);
    });

    test("renders play icon in overlay", () => {
      render(<ProgressiveSkillsAnimation />);
      const playIcons = screen.getAllByTestId("play-icon");
      expect(playIcons.length).toBeGreaterThanOrEqual(1);
    });
  });

  describe("chat input decorative", () => {
    test("renders decorative chat input", () => {
      render(<ProgressiveSkillsAnimation />);
      expect(screen.getByText("Ask iDeer anything...")).toBeInTheDocument();
    });
  });
});
