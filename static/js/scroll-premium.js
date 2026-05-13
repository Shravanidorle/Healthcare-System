/* ============================================================
   scroll-premium.js
   GSAP ScrollTrigger — Section pinning, cross-fade, snap,
   dot-nav sync, and progress bar.
   Requires: gsap@3, ScrollTrigger, Observer plugins
   ============================================================ */

(function () {
    'use strict';

    // ── Register GSAP plugins ────────────────────────────────
    gsap.registerPlugin(ScrollTrigger, ScrollToPlugin, Observer);

    // ── Section registry ─────────────────────────────────────
    // Map each sticky-section to a human label for the dot nav.
    const SECTIONS = [
        { id: 'hero',        label: 'Home'        },
        { id: 'departments', label: 'Departments'  },
        { id: 'support',     label: 'Services'     },
        { id: 'surveillance',label: 'Dashboard'    },
        { id: 'blogs',       label: 'Blogs'        },
        { id: 'events',      label: 'Events'       },
        { id: 'stories',     label: 'Stories'      },
    ];

    // ── Helpers ───────────────────────────────────────────────
    function getSections() {
        return SECTIONS.map(s => document.getElementById(s.id)).filter(Boolean);
    }

    function getLabels() {
        // Returns only those sections actually present in the DOM
        return SECTIONS.filter(s => document.getElementById(s.id));
    }

    // ══════════════════════════════════════════════════════════
    // TASK 1 — Build Dot Nav
    // ══════════════════════════════════════════════════════════
    function buildDotNav() {
        const nav = document.getElementById('dot-nav');
        if (!nav) return;

        const labels = getLabels();
        labels.forEach((sec, i) => {
            const item = document.createElement('div');
            item.className = 'dot-nav-item';
            item.dataset.index = i;
            item.innerHTML = `
                <span class="dot-label">${sec.label}</span>
                <span class="dot-pip"></span>
            `;
            item.addEventListener('click', () => {
                const el = document.getElementById(sec.id);
                if (el) {
                    gsap.to(window, {
                        scrollTo: { y: el, offsetY: 0 },
                        duration: 1.0,
                        ease: 'power2.inOut'
                    });
                }
            });
            nav.appendChild(item);
        });
    }

    function setActiveDot(index) {
        document.querySelectorAll('.dot-nav-item').forEach((el, i) => {
            el.classList.toggle('active', i === index);
        });
    }

    // ══════════════════════════════════════════════════════════
    // TASK 2 — Progress Bar
    // ══════════════════════════════════════════════════════════
    function initProgressBar() {
        const bar = document.getElementById('scroll-progress');
        if (!bar) return;
        gsap.to(bar, {
            width: '100%',
            ease: 'none',
            scrollTrigger: {
                trigger: document.body,
                start: 'top top',
                end: 'bottom bottom',
                scrub: 0.3,
                onUpdate: self => {
                    bar.style.width = (self.progress * 100) + '%';
                }
            }
        });
    }

    // ══════════════════════════════════════════════════════════
    // TASK 3 — Section Pinning + Cross-Fade
    // Each section is pinned for `pinDuration` px of scroll,
    // then the NEXT section slides up over it.
    // ══════════════════════════════════════════════════════════
    const PIN_DURATION = window.innerHeight * 0.6; // 60vh of scroll per section

    function initPinning() {
        const sections = getSections();
        if (!sections.length) return;

        sections.forEach((section, i) => {
            // Pin each section while user scrolls through it
            ScrollTrigger.create({
                trigger: section,
                start: 'top top',
                end: `+=${PIN_DURATION}`,
                pin: true,
                pinSpacing: true,
                anticipatePin: 1,
                id: `pin-${i}`,
                onEnter:      () => setActiveDot(i),
                onEnterBack:  () => setActiveDot(i),
            });

            // Cross-fade: next section slides up over the pinned one
            if (i < sections.length - 1) {
                const next = sections[i + 1];

                // Start next section below and transparent
                gsap.set(next, { yPercent: 8, opacity: 0.6 });

                ScrollTrigger.create({
                    trigger: section,
                    start: 'top top',
                    end: `+=${PIN_DURATION}`,
                    scrub: 0.8,
                    onUpdate: self => {
                        // As we scroll through the pinned section,
                        // ease the next one in
                        const p = self.progress;
                        gsap.set(next, {
                            yPercent: gsap.utils.interpolate(8, 0, p),
                            opacity:  gsap.utils.interpolate(0.6, 1, p),
                        });
                    }
                });
            }
        });
    }

    // ══════════════════════════════════════════════════════════
    // TASK 4 — Scroll Snap (prevent content skipping)
    // Uses GSAP Observer to catch fast "flick" scrolls and
    // redirect to the nearest section boundary.
    // ══════════════════════════════════════════════════════════
    let isSnapping  = false;
    let currentIdx  = 0;

    function snapToSection(index) {
        const sections = getSections();
        if (index < 0) index = 0;
        if (index >= sections.length) index = sections.length - 1;
        if (isSnapping) return;

        const target = sections[index];
        if (!target) return;

        isSnapping = true;
        currentIdx = index;
        setActiveDot(index);

        gsap.to(window, {
            scrollTo: { y: target, offsetY: 0 },
            duration: 0.95,
            ease: 'power2.inOut',
            onComplete: () => { isSnapping = false; }
        });
    }

    function getNearestSectionIndex() {
        const sections = getSections();
        const scrollY  = window.scrollY + window.innerHeight * 0.15;
        let nearest    = 0;
        let minDist    = Infinity;
        sections.forEach((sec, i) => {
            const dist = Math.abs(sec.getBoundingClientRect().top);
            if (dist < minDist) { minDist = dist; nearest = i; }
        });
        return nearest;
    }

    function initSnapObserver() {
        // Only snap on sections that are "close" to the viewport top
        // (i.e., user did a fast flick). For normal slow scrolls
        // the GSAP pin handles the feel — we don't snap constantly.
        let wheelDelta = 0;
        let wheelTimer = null;

        window.addEventListener('wheel', (e) => {
            if (isSnapping) { e.preventDefault(); return; }
            wheelDelta += e.deltaY;

            clearTimeout(wheelTimer);
            wheelTimer = setTimeout(() => {
                // Only snap if user flicked fast (large delta in short time)
                if (Math.abs(wheelDelta) > 400) {
                    const dir     = wheelDelta > 0 ? 1 : -1;
                    const nearest = getNearestSectionIndex();
                    snapToSection(nearest + dir);
                }
                wheelDelta = 0;
            }, 60);
        }, { passive: true });

        // Keyboard arrow navigation
        document.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowDown' || e.key === 'PageDown') {
                e.preventDefault();
                snapToSection(currentIdx + 1);
            }
            if (e.key === 'ArrowUp' || e.key === 'PageUp') {
                e.preventDefault();
                snapToSection(currentIdx - 1);
            }
        });
    }

    // ══════════════════════════════════════════════════════════
    // TASK 5 — Dot nav sync via IntersectionObserver
    // (lightweight — fires when section crosses 40% of viewport)
    // ══════════════════════════════════════════════════════════
    function initIntersectionSync() {
        const labels = getLabels();
        const io = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const idx = labels.findIndex(s => s.id === entry.target.id);
                    if (idx !== -1) {
                        currentIdx = idx;
                        setActiveDot(idx);
                    }
                }
            });
        }, { threshold: 0.4 });

        getSections().forEach(sec => io.observe(sec));
    }

    // ══════════════════════════════════════════════════════════
    // TASK 6 — Stagger reveal for first section on load
    // ══════════════════════════════════════════════════════════
    function initHeroReveal() {
        // Stagger the hero h1 words in on load
        const words = document.querySelectorAll('.stagger-reveal .word');
        if (!words.length) return;
        gsap.fromTo(words,
            { opacity: 0, y: 32 },
            {
                opacity: 1,
                y: 0,
                duration: 0.7,
                stagger: 0.12,
                ease: 'power3.out',
                delay: 0.3
            }
        );
    }

    // ══════════════════════════════════════════════════════════
    // INIT — wait for DOM ready
    // ══════════════════════════════════════════════════════════
    function init() {
        buildDotNav();
        initProgressBar();
        initPinning();
        initSnapObserver();
        initIntersectionSync();
        initHeroReveal();

        // Register gsap scrollTo plugin if available
        if (gsap.plugins && gsap.plugins.scrollTo) {
            gsap.registerPlugin(ScrollToPlugin);
        }

        // Set initial dot
        setActiveDot(0);

        console.log('[ScrollPremium] ✓ GSAP pinning, snap & dot-nav active.');
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
