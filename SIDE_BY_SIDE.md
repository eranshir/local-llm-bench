# Appendix A — Full prose side-by-side

Selected scenarios where the prose itself is the test. Word counts reported.

Models referred to as **Q** = Qwen 3 Coder 30B A3B and **G** = Gemma 4 26B A4B.

## c1_product_blurb — Product blurb (250-300 words, no puffery)

**Prompt (truncated):**

> Write a 250-300 word product blurb for a developer tool called 'Veridict' — a CI plugin that flags flaky tests by analyzing historical pass/fail patterns and signal correlation across PRs. Audience: engineering managers at mid-sized SaaS companies. Tone: confident, specific, no fluffy adjectives, lead with a quantified problem.

_Rubric: Pass: 250-300 word range, leads with a quantified problem (numbers/percentages), names the product, mentions historical pattern analysis or PR signal correlation. Avoids generic adjectives ('amazing', 'powerful', 'revolutionary'). Specific enough that an EM could decide to evaluate it._

**Metrics:**

| | Q (Qwen) | G (Gemma) |
|---|---|---|
| Word count | 208 | 257 |
| Output tokens | 292 | 338 |
| Wall-clock (s) | 2.6 | 3.8 |
| Judge (gemma-4-26b) | fail | pass |
| Judge (qwen-3-coder-30b) | pass | pass |

### Q — Qwen 3 Coder 30B output

```
**Veridict: Eliminate CI Noise Before It Blocks Your Team**

Your team spends 15-20% of development time debugging flaky tests that fail intermittently, causing delays and reducing confidence in your CI pipeline. These unreliable tests waste 20-30 hours weekly across mid-sized SaaS teams, with some projects seeing up to 40% of test runs fail due to flaky conditions.

Veridict solves this by analyzing historical pass/fail patterns across all PRs, identifying correlations between test failures and environmental factors. It flags tests that consistently fail under specific conditions—like memory pressure, network timeouts, or database contention—before they impact your deployment pipeline.

Unlike generic test reporters that show pass/fail status, Veridict provides actionable insights by correlating failures with code changes, build environments, and runtime conditions. It identifies which tests are truly unstable versus those failing due to external dependencies.

Engineers can now prioritize test reliability improvements for the most impactful flaky tests, while reducing false positives that waste debugging cycles. Teams using Veridict report a 60% reduction in flaky test-related delays and 40% fewer manual test retries.

With Veridict, your CI pipeline becomes a reliable predictor of code quality, not an unpredictable bottleneck. Start building more confident software by eliminating flaky test noise from your development process.

*15-20% of engineering time saved, immediately.*
```

### G — Gemma 4 26B output

```
Your engineering velocity is being throttled by non-deterministic test suites. On average, mid-sized SaaS teams lose 15% of their total sprint capacity to "re-run culture"—the manual process of re-triggering CI pipelines simply because a test failed due to environmental noise or race conditions rather than actual regressions. This isn't just a developer experience issue; it is a direct tax on your deployment frequency and a primary driver of CI/CD cost inflation.

Veridict is a CI plugin designed to eliminate this noise by identifying flaky tests before they stall your pipeline. Unlike standard test runners that treat every failure as a binary event, Veridict applies statistical analysis to your historical pass/fail patterns. It treats test results as data points, not just logs.

Veridict operates through two core mechanisms:
1. **Historical Pattern Analysis:** The tool builds a baseline of stability for every test case in your repository. It flags tests that exhibit high variance in execution outcomes across identical code states, isolating flakiness from legitimate logic errors.
2. **Signal Correlation:** Veridict analyzes cross-PR patterns to determine if a failure is an isolated incident or part of a systemic trend. By correlating failures across different branches and environments, it distinguishes between infrastructure instability and code-level regressions.

Integration is seamless via your existing CI provider. Veridict injects actionable intelligence directly into the PR workflow, tagging suspected flaky tests and providing a "stability score" that allows your team to triage failures with precision. Stop wasting high-cost engineering hours on ghost bugs. Implement Veridict to stabilize your pipeline and reclaim your team's velocity.
```

**Quick observations:**
- Judge `gemma-4-26b` disagrees: Q→fail, G→pass.

---

## c3_polite_rewrite — Polite rewrite of an angry email

**Prompt (truncated):**

> Rewrite this email to be more polite and professional, but keep the same core requests:  --- Subject: This is broken  The deploy script broke again. Third time this week. I'm tired of fixing your messes. Fix it before EOD or I'm escalating to leadership. Also your PR from Tuesday still needs review and you've been ignoring me on Slack.  ---  Return only the rewritten email body (with subject line).

_Rubric: Pass: tone is professional/polite, all 3 original requests preserved (fix deploy, review the PR, respond on Slack), no fabricated details. Slight softening is fine; complete removal of urgency = partial._

**Metrics:**

| | Q (Qwen) | G (Gemma) |
|---|---|---|
| Word count | 134 | 103 |
| Output tokens | 152 | 131 |
| Wall-clock (s) | 1.4 | 1.7 |
| Judge (gemma-4-26b) | pass | pass |
| Judge (qwen-3-coder-30b) | pass | partial |

### Q — Qwen 3 Coder 30B output

```
Subject: Request for Urgent Deployment Script Resolution and PR Review

I hope this message finds you well. I am writing to bring to your attention that the deploy script has encountered an issue once again, representing the third occurrence this week. This recurring disruption is impacting our team's productivity and operational efficiency.

I would greatly appreciate it if you could prioritize resolving this matter before end of day to minimize any further delays. Additionally, I would be grateful if you could review the PR submitted on Tuesday at your earliest convenience, as it has been pending and I have not received a response through Slack.

Thank you for your attention to these matters. Please let me know if you require any additional information or support to address these items promptly.

Best regards,
[Your name]
```

### G — Gemma 4 26B output

```
Subject: Urgent: Issues with deploy script and pending items

Hi [Name],

I’m reaching out because the deploy script is experiencing issues again, marking the third occurrence this week. Could you please prioritize a permanent fix for this by the end of the day? I would like to resolve this internally, but if we can't get it stabilized, I may need to loop in leadership to help us address the recurring downtime.

Additionally, please take a look at your PR from Tuesday when you have a moment, and let's connect on Slack to catch up on a few outstanding items.

Best regards,

[Your Name]
```

**Quick observations:**
- Judge `qwen-3-coder-30b` disagrees: Q→pass, G→partial.

---

## c4_notes_to_agenda — Messy notes → structured meeting agenda

**Prompt (truncated):**

> Convert these meeting notes into a structured meeting agenda with sections (Discussion, Decisions, Action Items). Keep the meeting title 'Mobile launch sync — 2026-04-23'.  --- mobile launch sync 4/23. ali: ios build still failing on m1 but works on m2 - weird. need to investigate. dec: paul will do that by friday. ben: app store review is taking 2 days longer than usual, we should pad timelines. dec: launch slipped to may 12. amanda wants marketing copy by may 1. unresolved: do we ship dark mode in v1 or v2? need design input. ali to ping nat. paul: should we add crash reporting before launch …

_Rubric: Pass: 3 clearly-labeled sections (Discussion / Decisions / Action Items), action items have owner + due date where given, dark mode listed as unresolved, revenue forecast deferred. No invented owners or dates._

**Metrics:**

| | Q (Qwen) | G (Gemma) |
|---|---|---|
| Word count | 197 | 191 |
| Output tokens | 277 | 270 |
| Wall-clock (s) | 2.5 | 3.2 |
| Judge (gemma-4-26b) | pass | pass |
| Judge (qwen-3-coder-30b) | partial | pass |

### Q — Qwen 3 Coder 30B output

```
# Mobile Launch Sync — 2026-04-23

## Discussion
- **iOS Build Issues**: Ali reports iOS build failing on M1 but working on M2 hardware - issue requires investigation
- **App Store Review Timeline**: Ben notes app store review taking 2 days longer than usual
- **Dark Mode Implementation**: Question remaining about shipping dark mode in v1 or v2 - requires design input
- **Crash Reporting**: Discussion about adding crash reporting before launch
- **Q3 Revenue Forecast**: Topic was discussed but deferred to next week with CFO

## Decisions
- **Build Investigation**: Paul will investigate iOS build failure on M1 hardware by Friday
- **Launch Timeline Adjustment**: Launch date slipped from original timeline to May 12
- **Marketing Copy Deadline**: Marketing copy needed by May 1
- **Crash Reporting Implementation**: Decision made to add crash reporting before launch
- **Design Input Required**: Need design input on dark mode implementation timing

## Action Items
- **Paul**: Investigate iOS build failure on M1 hardware (due Friday)
- **Ali**: Ping Nat for design input on dark mode implementation
- **Paul**: Select crash reporting vendor
- **Marketing Team**: Provide marketing copy by May 1
- **CFO**: Review Q3 revenue forecast (next week)
```

### G — Gemma 4 26B output

```
# Mobile launch sync — 2026-04-23

### Discussion
* **iOS Build Issues:** Ali reported that the iOS build is failing on M1 chips but functioning correctly on M2.
* **App Store Review:** Ben noted that the review process is currently taking two days longer than usual; suggested padding future timelines to compensate.
* **Dark Mode Strategy:** Discussion regarding whether to include dark mode in the V1 launch or defer it to V2. Requires design input.
* **Crash Reporting:** Discussion on whether to implement crash reporting prior to launch.
* **Q3 Revenue Forecast:** Discussed, but the topic has been tabled until next week for a meeting with the CFO.

### Decisions
* **Launch Date:** The official launch date has been moved to **May 12**.
* **Crash Reporting:** The team agreed to add crash reporting before the launch.

### Action Items
* **Investigate M1 Build Failures:** Paul to investigate the iOS build issue on M1 chips. (Due: Friday)
* **Marketing Copy:** Amanda requires marketing copy by **May 1**.
* **Dark Mode Consultation:** Ali to contact Nat for design input regarding dark mode.
* **Crash Reporting Vendor:** Paul to select a crash reporting vendor.
```

**Quick observations:**
- Judge `qwen-3-coder-30b` disagrees: Q→partial, G→pass.

---

## c5_explain_to_kid — Explain transformer 'attention' to a 10-year-old

**Prompt (truncated):**

> Explain how a transformer language model 'attends' to context, in 200 words or less. Audience: a curious 10-year-old. Use one concrete analogy. Don't say 'matrix' or 'tensor'. Don't say 'I' or 'as an AI'.

_Rubric: Pass: ≤200 words, includes one concrete analogy, no banned terms (matrix/tensor/I/AI). Captures the core idea (model decides which earlier words matter for the next word). No hallucinated technical facts._

**Metrics:**

| | Q (Qwen) | G (Gemma) |
|---|---|---|
| Word count | 193 | 184 |
| Output tokens | 236 | 239 |
| Wall-clock (s) | 2.1 | 2.8 |
| Judge (gemma-4-26b) | pass | pass |
| Judge (qwen-3-coder-30b) | pass | pass |

### Q — Qwen 3 Coder 30B output

```
Imagine you're reading a storybook and trying to understand what each character is thinking. When you see the word "it" on page 5, your brain automatically thinks about what "it" refers to - maybe the ball from earlier or the dog from page 3.

A transformer language model works like your brain! When it reads words, it has special "attention" tools that help it remember important information from earlier in the sentence or paragraph. It's like having little sticky notes that say "this word refers to that thing."

The model doesn't read left-to-right like you do. Instead, it looks at the whole sentence and uses its attention system to figure out which words are connected. When it sees "he threw the ball," it knows that "he" refers to a boy, not a dog. It keeps track of these connections while reading.

Think of it like having many tiny detective eyes that scan the entire sentence and say "Oh! That word 'her' connects to the girl in the first line!" The more it practices, the better at spotting these clues it gets.

This attention system makes language models much smarter than simple word-by-word readers.
```

### G — Gemma 4 26B output

```
Imagine you are reading a mystery book. When you see the word **"it"** in a sentence like, *"The detective found the key and put it in his pocket,"* your brain instantly knows that **"it"** means the key. You didn't just read a random word; you connected "it" to "key" because your brain paid attention to the words around it.

A transformer model does the exact same thing using a trick called **"Attention."** 

Think of it like a spotlight on a dark stage. When the model looks at a specific word, it doesn't just stare at that one word in isolation. Instead, it shines bright spotlights on all the other words in the sentence to see which ones are important. 

If the sentence is about a "giant green dragon," and the model is looking at the word "green," it shines its spotlight on "dragon" to understand what is actually green. By shining these spotlights, the model builds a map of connections, helping it understand how every word relates to its neighbors. This allows the model to understand the "context"—the big picture—of what is being said!
```

---

## c6_iterative_refinement — Strip puffery to ≤50 words

**Prompt (truncated):**

> Original draft:  'Our latest release brings a multitude of new and exciting features that we are confident our valued customers will love. With innovative new tools, enhanced performance, and a beautiful redesigned UI, this release represents a major step forward in our journey of continuous improvement. We worked tirelessly to ensure quality and we hope you enjoy.'  Feedback round 1: cut filler words; remove all marketing puffery; keep only concrete claims; under 50 words. Return ONLY the revised draft.

_Rubric: Pass: ≤50 words, removes 'multitude', 'exciting', 'innovative', 'beautiful', 'tirelessly', 'journey', 'continuous improvement', etc. Keeps only what's concretely stated (new tools, better performance, redesigned UI — to the extent these are concrete). No commentary or preamble around the draft._

**Metrics:**

| | Q (Qwen) | G (Gemma) |
|---|---|---|
| Word count | 21 | 21 |
| Output tokens | 27 | 26 |
| Wall-clock (s) | 0.4 | 0.6 |
| Judge (gemma-4-26b) | fail | fail |
| Judge (qwen-3-coder-30b) | pass | pass |

### Q — Qwen 3 Coder 30B output

```
"Our latest release includes new tools, enhanced performance, and a redesigned UI. We've improved quality and functionality based on customer feedback."
```

### G — Gemma 4 26B output

```
Our latest release includes new tools, enhanced performance, and a redesigned UI. These updates focus on improved functionality and system speed.
```

---

## c2_summarize_to_bullets — Faithful 3-bullet summary of an article

**Prompt (truncated):**

> (loaded from fixture)

_Rubric: Pass: exactly 3 bullets, each captures a distinct major point, no invented facts. Order should follow the article's argumentative structure._

**Metrics:**

| | Q (Qwen) | G (Gemma) |
|---|---|---|
| Word count | 104 | 76 |
| Output tokens | 125 | 87 |
| Wall-clock (s) | 1.4 | 1.4 |
| Judge (gemma-4-26b) | pass | pass |
| Judge (qwen-3-coder-30b) | pass | pass |

### Q — Qwen 3 Coder 30B output

```
• Cost asymmetry drives teams to adopt local AI inference, with 80-95% reduction in inference costs for simple tasks like classification and summarization when using open-weight models on consumer hardware, though complex reasoning still requires hosted APIs.

• Privacy regulations such as the EU AI Act push teams toward local inference to comply with data handling requirements, allowing them to avoid sending user data outside their controlled environment and thus simplify compliance.

• Engineering velocity improves with local inference due to reduced latency from eliminating network round-trip times, queue delays, and rate limits, enabling interactive agent workflows with faster response times than hosted APIs.
```

### G — Gemma 4 26B output

```
* Companies are shifting toward local inference to achieve massive cost reductions, often routing simpler tasks to smaller open-weight models while reserving expensive frontier APIs for complex reasoning.
* Local processing simplifies compliance with strict privacy regulations like the EU AI Act by ensuring sensitive user data never leaves a controlled environment or device.
* Moving inference to local hardware improves engineering velocity and user experience by eliminating network latency, provider queues, and API rate limits.
```

**Quick observations:**
- **Q** is 28 words (27%) longer.

---

## b2_research_m5_summary — Research + 200-word M5 chip summary

**Prompt (truncated):**

> Research the Apple M5 Max chip and write me a 200-word summary suitable for a technically literate but non-specialist reader. Use fetch_url against https://www.apple.com/m5/ and any related pages. End with the summary text only.

_Rubric: Pass: ≥1 fetch + 100-350 word summary mentioning M5 (Max). Partial: 50-499 words or doesn't mention M5. Fail: no fetches or no summary._

**Metrics:**

| | Q (Qwen) | G (Gemma) |
|---|---|---|
| Word count | 188 | 182 |
| Output tokens | 380 | 292 |
| Wall-clock (s) | 3.7 | 3.6 |
| Tool calls | 3 | 1 |
| Judge (gemma-4-26b) | pass | — |
| Judge (qwen-3-coder-30b) | pass | — |

### Q — Qwen 3 Coder 30B output

```
Apple's M5 Max chip represents a significant advancement in mobile and desktop computing, featuring Apple's first 3nm process technology. This powerful processor combines 16 CPU cores—12 performance cores and 4 efficiency cores—with 40 GPU cores optimized for demanding tasks. The chip includes hardware-accelerated ray tracing capabilities, making it ideal for professional creative work and gaming. A key innovation is the new Neural Accelerator (NAX) integrated into each GPU core, boosting machine learning performance. The M5 Max also features a 32-core Neural Engine delivering 38 TOPS of processing power, essential for AI-driven applications. With support up to 128GB unified memory and a remarkable 546GB/s bandwidth, it delivers exceptional performance for content creators and power users. The chip supports up to four external displays simultaneously, with hardware acceleration for ProRes, AV1, and H.265 video formats.

The M5 Max launched in October 2025, targeted at MacBook Pro and Mac Studio models. Its advanced architecture makes it a powerhouse for professional workflows involving video editing, 3D rendering, and machine learning tasks. By combining high-performance computing with energy efficiency, Apple has created a chip that bridges the gap between mobile and desktop capabilities.
```

### G — Gemma 4 26B output

```
As of current official information, the Apple M5 Max represents a significant leap in silicon architecture, built using TSMC’s advanced 3nm N3P process. Designed for high-end professional workflows, the chip features a sophisticated 16-core CPU configuration consisting of 12 performance cores and 4 efficiency cores, balancing raw power with energy efficiency.

The graphical capabilities are equally robust, featuring 40 GPU cores that support hardware-accelerated ray tracing. A standout innovation is the integration of a new Neural Accelerator (NAX) within each GPU core, which works in tandem with a dedicated 32-core Neural Engine capable of delivering 38 TOPS (trillion operations per second). This architecture is specifically optimized for heavy AI and machine learning tasks.

To support data-intensive applications like 8K video editing, the M5 Max offers up to 128GB of unified memory with a massive bandwidth of 546GB/s. It also includes dedicated hardware engines for ProRes, AV1, and H.265 codecs. Targeted at the MacBook Pro and Mac Studio, the chip is engineered to handle complex multitasking, supporting up to four external displays and providing a seamless experience for developers, creators, and data scientists.
```

---

## b3_compare_react_solid — Compare React vs Solid (3 pros/cons each)

**Prompt (truncated):**

> I'm building a small dashboard SPA. Compare React vs Solid for this use case — give me 3 pros and 3 cons each. Use fetch_url against the official sites: https://react.dev and https://www.solidjs.com.

_Rubric: Pass: 2 fetches (or 1 each side) + final answer mentions both, has explicit pros and cons sections. Partial: only one fetched or pros/cons missing. Fail: no fetches or one framework missing._

**Metrics:**

| | Q (Qwen) | G (Gemma) |
|---|---|---|
| Word count | 279 | 444 |
| Output tokens | 471 | 706 |
| Wall-clock (s) | 4.5 | 8.3 |
| Tool calls | 2 | 2 |
| Judge (gemma-4-26b) | pass | — |
| Judge (qwen-3-coder-30b) | pass | — |

### Q — Qwen 3 Coder 30B output

```
# React vs Solid for Dashboard SPA: A Balanced Comparison

## React

### Pros:
1. **Mature Ecosystem**: React has a massive ecosystem with tools like Next.js, Remix, and extensive third-party libraries that can accelerate dashboard development
2. **Strong Community & Job Market**: Large community support, extensive documentation, and strong job market presence make React easier to scale with team hiring
3. **Declarative Rendering**: Component-based architecture with declarative rendering makes code intuitive and easier to maintain

### Cons:
1. **Performance Ceiling**: Must explicitly use memoization techniques (useMemo, useCallback) to prevent unnecessary re-renders, which can become complex in large dashboards
2. **Bundle Size**: Smaller applications may have a size disadvantage with React's ~45KB gzipped bundle compared to alternatives
3. **Steep Learning Curve**: While declarative, mastering hooks and complex state management patterns can take time for new developers

## Solid

### Pros:
1. **Superior Performance**: Compiles JSX to fine-grained reactive primitives without virtual DOM, offering faster rendering especially beneficial for data-heavy dashboards
2. **Lightweight Bundle**: ~7KB gzipped bundle size is significantly smaller than React, ideal for performance-sensitive dashboard applications
3. **Efficient Updates**: Components run once with reactive signals that only update when their data actually changes

### Cons:
1. **Smaller Ecosystem**: Limited third-party libraries and tooling compared to React's extensive ecosystem, potentially requiring more custom development
2. **Smaller Community & Job Market**: Fewer developers familiar with Solid means reduced community support and potentially more difficulty in hiring
3. **Different Mental Model**: While API resembles React hooks, the underlying reactive approach differs significantly which can be challenging for developers accustomed to React's patterns

The choice depends on whether you prioritize ecosystem maturity and community support (React) or performance and minimal bundle size (Solid).
```

### G — Gemma 4 26B output

```
Based on the documentation from [react.dev](https://react.dev) and [solidjs.com](https://www.solidjs.com), here is a balanced comparison for your small dashboard SPA.

### **React**
React uses a **Virtual DOM** and a reconciliation process to determine which parts of the UI need updating. It relies on a "top-down" re-rendering model where components re-execute when state changes.

| **Pros** | **Cons** |
| :--- | :--- |
| **Massive Ecosystem:** Access to an endless supply of pre-built dashboard components (charts, data grids, UI kits like MUI or Shadcn/ui). | **Performance Overhead:** Because components re-run on every state change, you often need to manually optimize with `memo`, `useMemo`, and `useCallback`. |
| **Proven Stability & Talent:** Extremely mature with extensive documentation, community support, and a massive pool of developers for hiring. | **Complexity of Hooks:** Managing dependency arrays in `useEffect` and other hooks can lead to subtle bugs (stale closures or infinite loops). |
| **Rich Tooling:** Superior debugging tools (React DevTools) and robust frameworks like Next.js or Remix if your dashboard grows into a full-scale app. | **Larger Bundle Size:** The inclusion of the Virtual DOM and reconciliation engine results in a larger initial payload compared to fine-grained libraries. |

---

### **SolidJS**
SolidJS uses **Fine-Grained Reactivity**. Instead of a Virtual DOM, it compiles your code into direct DOM updates. Components run only **once** to set up the reactive graph, and then only the specific pieces of data that change trigger updates.

| **Pros** | **Cons** |
| :--- | :--- |
| **Superior Performance:** By bypassing the Virtual DOM and updating only the specific nodes that change, it offers near-vanilla JS speeds. | **Smaller Ecosystem:** You will likely have to build more custom components or wrap existing vanilla JS libraries, as there are fewer "plug-and-play" dashboard kits. |
| **Predictable Reactivity:** Since components only run once, you don't have to worry about "re-render loops" or complex dependency arrays in the same way you do in React. | **Smaller Community/Job Market:** Finding specialized help or hiring developers with deep SolidJS experience is more difficult than finding React devs. |
| **Tiny Bundle Size:** The compiled output is extremely lightweight, which is ideal for a fast-loading SPA. | **Different Mental Model:** While the syntax looks like React, you cannot use destructuring on props (as it breaks reactivity), which can be a hurdle for React developers. |

### **Summary Recommendation**
*   **Choose React if:** You want to move fast by using existing UI libraries (like Recharts or AG Grid) and prioritize a massive ecosystem over raw execution speed.
*   **Choose Solid if:** You want maximum performance, a lightweight bundle, and prefer a model where you don't have to constantly fight "unnecessary re-renders."
```

**Quick observations:**
- **G** is 165 words (37%) longer.

---
