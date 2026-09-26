import { useEffect, useRef } from 'react';
import { driver, type DriveStep, type Driver } from 'driver.js';
import type { MapOverlayPanel } from '../map/MapOverlays';
import 'driver.js/dist/driver.css';

const tutorialCompletedKey = 'hisar-tutorial-completed';
type TutorialStepKey =
  | 'welcome'
  | 'map-sidebar'
  | 'route-controls'
  | 'quick-filters'
  | 'active-track-marker'
  | 'operation-summary'
  | 'priority-vehicles'
  | 'analyst-review'
  | 'agent'
  | 'track-list'
  | 'timeline'
  | 'notifications'
  | 'settings'
  | 'help'
  | 'completed';

type TutorialSnapshot = {
  bottomOpen: boolean;
  helpOpen: boolean;
  notificationsOpen: boolean;
  settingsOpen: boolean;
  sidebarOpen: boolean;
  timelineCompact: boolean;
};

export type AppTutorialProps = {
  ready: boolean;
  runId: number;
  bottomOpen: boolean;
  helpOpen: boolean;
  notificationsOpen: boolean;
  settingsOpen: boolean;
  sidebarOpen: boolean;
  timelineCompact: boolean;
  setBottomOpen: (open: boolean) => void;
  setHelpOpen: (open: boolean) => void;
  setNotificationsOpen: (open: boolean) => void;
  setSettingsOpen: (open: boolean) => void;
  setSidebarOpen: (open: boolean) => void;
  setTimelineCompact: (compact: boolean) => void;
  setTourActive: (active: boolean) => void;
  setTourOverlayPanel: (panel: MapOverlayPanel | undefined) => void;
};

const targets: Partial<Record<TutorialStepKey, string>> = {
  'map-sidebar': '[data-tour="map-sidebar"]',
  'route-controls': '[data-tour="route-controls"]',
  'quick-filters': '[data-tour="quick-filters"]',
  'active-track-marker': '[data-tour="active-track-marker"]',
  'operation-summary': '[data-tour="operation-summary-panel"]',
  'priority-vehicles': '[data-tour="priority-vehicles-panel"]',
  'analyst-review': '[data-tour="analyst-review-panel"]',
  agent: '[data-tour="agent-panel"]',
  'track-list': '[data-tour="track-list"]',
  timeline: '[data-tour="timeline"]',
  notifications: '[data-tour="notifications"]',
  settings: '[data-tour="settings"]',
  help: '[data-tour="help"]',
};

const tourSteps: DriveStep[] = [
  {
    data: { key: 'welcome' satisfies TutorialStepKey },
    popover: {
      title: 'HİSAR Operasyon Merkezi',
      description: 'Harita, iz analizi, zaman çizgisi ve karar destek araçlarını kısa bir turla inceleyelim.',
      side: 'bottom',
      align: 'center',
    },
  },
  {
    element: targets['map-sidebar'],
    data: { key: 'map-sidebar' satisfies TutorialStepKey },
    popover: {
      title: 'Harita katmanları',
      description: 'Sol harita panelinden katmanları, iz aramasını ve harita üzerindeki temel görünüm seçeneklerini yönetebilirsiniz.',
      side: 'right',
      align: 'start',
    },
  },
  {
    element: targets['route-controls'],
    data: { key: 'route-controls' satisfies TutorialStepKey },
    popover: {
      title: '2D / 3D ve rota kontrolleri',
      description: '2D/3D görünüm ve araç rota izlerini buradan yönetebilirsiniz.',
      side: 'bottom',
      align: 'start',
    },
  },
  {
    element: targets['quick-filters'],
    data: { key: 'quick-filters' satisfies TutorialStepKey },
    popover: {
      title: 'Hızlı filtreler',
      description: 'Haritadaki izleri risk, araç, senaryo ve bölge gibi operasyonel kriterlere göre hızlıca filtreleyin.',
      side: 'bottom',
      align: 'end',
    },
  },
  {
    element: targets['active-track-marker'],
    data: { key: 'active-track-marker' satisfies TutorialStepKey },
    popover: {
      title: 'Haritadaki izler',
      description: 'Araç izleri risk ve durumlarına göre haritada gösterilir. Bir ize tıklayarak detayına ulaşabilirsiniz.',
      side: 'top',
      align: 'center',
    },
  },
  {
    element: targets['operation-summary'],
    data: { key: 'operation-summary' satisfies TutorialStepKey },
    popover: {
      title: 'Operasyon Özeti',
      description: 'Genel operasyon durumunu ve kritik metrikleri buradan görüntüleyebilirsiniz.',
      side: 'left',
      align: 'start',
    },
  },
  {
    element: targets['priority-vehicles'],
    data: { key: 'priority-vehicles' satisfies TutorialStepKey },
    popover: {
      title: 'Öncelikli Araçlar',
      description: 'Önceliklendirilmiş yüksek riskli izleri hızlıca inceleyebilirsiniz.',
      side: 'left',
      align: 'start',
    },
  },
  {
    element: targets['analyst-review'],
    data: { key: 'analyst-review' satisfies TutorialStepKey },
    popover: {
      title: 'Analist Onayı',
      description: 'İnsan değerlendirmesi gereken kararlar bu alanda yönetilir.',
      side: 'left',
      align: 'start',
    },
  },
  {
    element: targets.agent,
    data: { key: 'agent' satisfies TutorialStepKey },
    popover: {
      title: 'Ajan',
      description: 'Doğal dil ile sisteme soru sorabilir, izler ve raporlar hakkında karar desteği alabilirsiniz.',
      side: 'left',
      align: 'start',
    },
  },
  {
    element: targets['track-list'],
    data: { key: 'track-list' satisfies TutorialStepKey },
    popover: {
      title: 'Tüm İz Kayıtları',
      description: 'Tüm track kayıtlarını arayabilir, filtreleyebilir ve karşılaştırabilirsiniz.',
      side: 'top',
      align: 'center',
    },
  },
  {
    element: targets.timeline,
    data: { key: 'timeline' satisfies TutorialStepKey },
    popover: {
      title: 'Timeline',
      description: 'Operasyon akışını zaman içinde oynatabilir ve geçmiş durumu inceleyebilirsiniz.',
      side: 'top',
      align: 'center',
    },
  },
  {
    element: targets.notifications,
    data: { key: 'notifications' satisfies TutorialStepKey },
    popover: {
      title: 'Bildirimler',
      description: 'İzlemeye alınan araçlardaki önemli değişiklikleri buradan takip edebilirsiniz.',
      side: 'bottom',
      align: 'end',
    },
  },
  {
    element: targets.settings,
    data: { key: 'settings' satisfies TutorialStepKey },
    popover: {
      title: 'Ayarlar',
      description: 'Tema, yazı boyutu, insan onayı ve sistem durumunu buradan yönetebilirsiniz.',
      side: 'bottom',
      align: 'end',
    },
  },
  {
    element: targets.help,
    data: { key: 'help' satisfies TutorialStepKey },
    popover: {
      title: 'Yardım',
      description: 'Kullanım kılavuzuna ve uygulama turuna buradan tekrar ulaşabilirsiniz.',
      side: 'bottom',
      align: 'end',
    },
  },
  {
    data: { key: 'completed' satisfies TutorialStepKey },
    popover: {
      title: 'Hazırsınız',
      description: 'HİSAR arayüzündeki temel araçları artık kullanabilirsiniz.',
      side: 'bottom',
      align: 'center',
    },
  },
];

function hasCompletedTutorial() {
  try {
    return window.localStorage.getItem(tutorialCompletedKey) === 'true';
  } catch {
    return false;
  }
}

function markTutorialCompleted() {
  try {
    window.localStorage.setItem(tutorialCompletedKey, 'true');
  } catch {
    /* localStorage may be unavailable. */
  }
}

function wait(ms = 80) {
  return new Promise(resolve => window.setTimeout(resolve, ms));
}

async function waitForElement(selector: string | undefined, timeout = 1400) {
  if (!selector) return true;
  const startedAt = performance.now();
  while (performance.now() - startedAt < timeout) {
    const element = document.querySelector(selector);
    if (element instanceof HTMLElement && element.offsetParent !== null) return true;
    await wait(60);
  }
  return false;
}

function stepKey(step: DriveStep | undefined): TutorialStepKey {
  return (step?.data?.key ?? 'welcome') as TutorialStepKey;
}

export function AppTutorial({
  ready,
  runId,
  bottomOpen,
  helpOpen,
  notificationsOpen,
  settingsOpen,
  sidebarOpen,
  timelineCompact,
  setBottomOpen,
  setHelpOpen,
  setNotificationsOpen,
  setSettingsOpen,
  setSidebarOpen,
  setTimelineCompact,
  setTourActive,
  setTourOverlayPanel,
}: AppTutorialProps) {
  const driverRef = useRef<Driver | null>(null);
  const autoStarted = useRef(false);
  const snapshotRef = useRef<TutorialSnapshot | null>(null);
  const latestStateRef = useRef<TutorialSnapshot>({
    bottomOpen,
    helpOpen,
    notificationsOpen,
    settingsOpen,
    sidebarOpen,
    timelineCompact,
  });
  const cleanedUp = useRef(false);

  useEffect(() => () => driverRef.current?.destroy(), []);
  useEffect(() => {
    latestStateRef.current = {
      bottomOpen,
      helpOpen,
      notificationsOpen,
      settingsOpen,
      sidebarOpen,
      timelineCompact,
    };
  }, [bottomOpen, helpOpen, notificationsOpen, settingsOpen, sidebarOpen, timelineCompact]);

  useEffect(() => {
    if (!ready) return;
    const forced = runId > 0;
    if (!forced && (autoStarted.current || hasCompletedTutorial())) return;
    autoStarted.current = true;

    const prepareStep = async (index: number) => {
      const key = stepKey(tourSteps[index]);
      setSettingsOpen(false);
      setHelpOpen(false);
      setNotificationsOpen(false);

      if (key === 'operation-summary') setTourOverlayPanel('summary');
      else if (key === 'priority-vehicles') setTourOverlayPanel('priority');
      else if (key === 'analyst-review') setTourOverlayPanel('reviews');
      else if (key === 'agent') setTourOverlayPanel('chat');
      else setTourOverlayPanel(null);

      if (key === 'map-sidebar') setSidebarOpen(true);
      if (key === 'track-list' || key === 'timeline') setBottomOpen(true);

      await wait(140);
      await waitForElement(typeof tourSteps[index].element === 'string' ? tourSteps[index].element : undefined);
    };

    const restoreAfterTour = () => {
      if (cleanedUp.current) return;
      cleanedUp.current = true;
      markTutorialCompleted();
      const snapshot = snapshotRef.current;
      setTourOverlayPanel(undefined);
      setTourActive(false);
      if (snapshot) {
        setBottomOpen(snapshot.bottomOpen);
        setHelpOpen(snapshot.helpOpen);
        setNotificationsOpen(snapshot.notificationsOpen);
        setSettingsOpen(snapshot.settingsOpen);
        setSidebarOpen(snapshot.sidebarOpen);
        setTimelineCompact(snapshot.timelineCompact);
      }
      snapshotRef.current = null;
    };

    const moveTo = async (tour: Driver, index: number) => {
      const boundedIndex = Math.max(0, Math.min(tourSteps.length - 1, index));
      await prepareStep(boundedIndex);
      tour.moveTo(boundedIndex);
      window.setTimeout(() => tour.refresh(), 120);
    };

    const startTimer = window.setTimeout(() => {
      snapshotRef.current = latestStateRef.current;
      cleanedUp.current = false;
      setTourActive(true);

      driverRef.current?.destroy();
      const tour = driver({
        steps: tourSteps,
        animate: true,
        smoothScroll: true,
        allowClose: true,
        allowScroll: true,
        overlayOpacity: 0.62,
        stagePadding: 8,
        stageRadius: 8,
        popoverClass: 'hisar-driver-popover',
        showButtons: ['previous', 'next', 'close'],
        showProgress: true,
        progressText: '{{current}} / {{total}}',
        nextBtnText: 'İleri',
        prevBtnText: 'Geri',
        doneBtnText: 'Bitir',
        overlayClickBehavior: 'close',
        skipMissingElement: true,
        waitForElement: 1200,
        onNextClick: (_element, _step, opts) => {
          const nextIndex = (opts.index ?? 0) + 1;
          if (nextIndex >= tourSteps.length) {
            restoreAfterTour();
            opts.driver.destroy();
            return;
          }
          void moveTo(opts.driver, nextIndex);
        },
        onPrevClick: (_element, _step, opts) => {
          void moveTo(opts.driver, (opts.index ?? 0) - 1);
        },
        onCloseClick: (_element, _step, opts) => {
          restoreAfterTour();
          opts.driver.destroy();
        },
        onDoneClick: (_element, _step, opts) => {
          restoreAfterTour();
          opts.driver.destroy();
        },
        onDestroyed: restoreAfterTour,
        onPopoverRender: popover => {
          popover.closeButton.textContent = 'Atla';
          popover.closeButton.setAttribute('aria-label', 'Turu atla');
        },
      });

      driverRef.current = tour;
      void prepareStep(0).then(() => tour.drive(0));
    }, forced ? 120 : 650);

    return () => window.clearTimeout(startTimer);
  }, [
    ready,
    runId,
    setBottomOpen,
    setHelpOpen,
    setNotificationsOpen,
    setSettingsOpen,
    setSidebarOpen,
    setTimelineCompact,
    setTourActive,
    setTourOverlayPanel,
  ]);

  return null;
}
