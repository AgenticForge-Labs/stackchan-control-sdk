# SDK, CLI, and performer integration plan

Status: planning and source inspection, 2026-10-29. No new hardware behavior
has been implemented or physically exercised for this plan.

The full cross-repository implementation and acceptance plan is maintained in
`forge-puppeteer/docs/ROBOT_MCP_IMPLEMENTATION_PLAN.md`. Implementation has
started with Puppeteer's metadata contracts; device integration remains planned.

## StackChan local exit

- [ ] Provide a discoverable touchscreen action to end EXT CONTROL and return
  to the launcher. The operator currently cannot find a usable exit.
- Existing source already creates a home indicator with a `close()` callback;
  inspect visibility, layering and touch handling with the enlarged avatar before
  deciding whether to repair that control or add a clearer exit affordance.
- Acceptance: exit during idle and active control; stop the control service,
  cancel pending work through its existing shutdown path, preserve the intended
  servo hold behavior, release the avatar/UI, and require a new session after
  reentry. Verify on hardware under separate operator authorization.
- This item is explicitly deferred; do not implement it as part of research.

## Findings: Reachy Mini

The local forge-reachy baseline pins Conversation App commit
`5ab905d018de8d88f07444ca57677b2ffbe762ca` and SDK `1.10.0rc5`.
Reuse that baseline rather than silently advancing dependencies.

- The SDK provides hardware access and recorded-move primitives. The Conversation
  App adds semantic tool dispatch and a MovementManager with queued primary moves
  and idle breathing.
- `tools/play_emotion.py` lazily loads SDK `RecordedMoves` from
  `pollen-robotics/reachy-mini-emotions-library`, resolves a semantic request to a
  named clip, wraps it in `EmotionQueueMove`, and calls `queue_move`.
  Its response means queued, not physically completed. Unresolved requests can
  fall back to a random curated clip; scripted performance needs stricter resolution.
- `dance_emotion_moves.py` adapts clips to the SDK `Move` interface:
  `duration` and `evaluate(t)` yielding head pose, antennas and body yaw.
- The pinned app enables the daemon's audio-reactive wobbler through
  `robot.enable_wobbling()`. Audio must use the matching media pipeline for this
  mechanism; arbitrary external audio playback is not automatically synchronized.
- The Conversation App consumes remote MCP tools through its tool infrastructure.
  That is distinct from exposing its native behavior runtime as an MCP server.
- Community example: ArturSkowronski/reachy-mini-mcp exposes FastMCP tools which
  call `ReachyMini` directly. Its emotion mapping is custom choreography, not the
  same catalog/runtime as Pollen's recorded emotion tool. Treat it as a reference,
  not an already-compatible integration with the pinned Conversation App.

Sources:
- https://github.com/pollen-robotics/reachy_mini_conversation_app/tree/5ab905d018de8d88f07444ca57677b2ffbe762ca
- https://github.com/ArturSkowronski/reachy-mini-mcp/blob/main/reachy.py
- Local forge-reachy/config/upstream.env and upstream checkout.

## Proposed Puppeteer integration

Primary execution path: Studio performance scripts drive Puppeteer's deterministic
executor, which largely invokes the device MCP servers. MCP is a shared execution
interface for scripted clients and conversational agents; it does not imply an
LLM chooses each action. Conversational use is a valuable secondary client of the
same controls, behavior catalogs and execution lifecycle.

Compile/resolve scripted cues to exact device actions and asset revisions before
execution. Preserve cue IDs, action IDs, timestamps, completion/cancellation and
failure policy. Use a monotonic timeline and explicit late-cue policy; do not rely
on transport arrival time for precise synchronization. Submit timed work to local
device execution where supported and report timing limitations honestly. Scripted
resolution must not silently choose random emotions or substitute assets.

Both scripted and conversational callers use the same validation, authority,
resource arbitration and device ownership. Define explicit control acquisition
and handoff so a conversation cannot interfere with a running scripted take.
Direct Python APIs remain useful for development and embedding, but are not a
substitute for validating the primary scripted-over-MCP execution path.

Direction clarified: Puppeteer should own reusable cross-device behavior
coordination. Reuse Reachy's motion assets and SDK execution primitives; the
Conversation App is an upstream reference and optional client/integration, not
a required running dependency for scripted performance.

Build deployment artifacts from a manifest pinning the Reachy SDK version,
motion dataset revision, selected files and hashes, upstream reference commit,
and license/attribution records. Bundle or cache the selected JSON trajectories
and optional audio during build so playback does not depend on network access.
Keep downloaded upstream assets separate from custom authored behaviors. Check
the installed SDK loader's support for the packaged asset location; add a narrow
adapter if needed rather than assuming a relocated cache is supported.

The official emotions dataset currently declares Apache-2.0 and documents JSON
trajectories plus audio sidecars. Preserve applicable licenses/notices and label
modified files. Availability of a hosted repository is not a permanence guarantee;
retain permitted pinned snapshots. Update dependencies/assets deliberately and
test loading, timing, cancellation and SDK compatibility before advancing pins.

Load behavior providers into a versioned catalog per performer. Preserve upstream
clip IDs and provenance; add custom behaviors under separate namespaces, with
explicit aliases for semantic names such as `thinking`. Example proposed IDs:
`reachy.default/thoughtful1`, `reachy.custom/listen_to_stackchan`,
`stackchan.custom/thinking`, `soarm.custom/acknowledge`.

The adapter discovers supported behaviors and resolves a semantic request to an
exact implementation before execution. Record resolved IDs, asset revisions,
parameters and any random seed in the take. Unknown behaviors fail explicitly;
alternative embodiments require explicit mappings.

Use a common lifecycle: discover, validate/prepare, start, observe completion,
cancel. Include readiness, duration when known, resource claims, parameter limits
and provenance. Primary motion, idle and speech overlays need explicit arbitration.
Idle should be opt-in during scripted takes. Device APIs retain their native units
and safety/calibration checks below this contract.

Prefer a single owning runtime per device. SDK/CLI/MCP are entry points to shared
execution logic. An optional Puppeteer MCP server may expose custom behaviors,
but must submit to that same device owner, not start a competing movement loop.
Puppeteer itself can call adapters directly; MCP need not sit inside every cue.

For Reachy, prototype reuse of the pinned SDK recorded-move API first. Determine
which app behavior helpers can be supported through composition or a narrow bridge
before depending on private app internals. If the Conversation App stays active,
custom moves must enter its existing movement manager. A standalone Puppeteer
runtime must explicitly own equivalent scheduling and disable competing app control.

## StackChan equivalents

- Native SDK/CLI: inspect capabilities/state, face features, head pose, lights,
  completion events and stop; keep probe diagnostics available separately.
- Behavior examples: acknowledge = bounded pitch nod plus face cue; thinking =
  yaw/pitch pose plus eye/mouth changes; surprise = widened features and head lift;
  speaking = audio-timed mouth changes plus bounded head emphasis; idle = blinking
  and optionally small authorized head changes.
- These are authored equivalents, not direct Reachy trajectory conversions.
  StackChan has yaw/pitch and a rendered face, without Reachy's full head/antenna
  articulation. Keep recipes/assets in examples initially, then promote stable
  reusable performers into Puppeteer providers.
- Native animation playback remains gated in current firmware. Establish complete
  validated keyframes and timing/cancellation semantics before using it. Do not
  assume a Reachy-rate streaming loop is suitable for the USB command interface.

## SO-ARM101 equivalents

The SDK already has TrajectoryLibrary, MotionSequence/SequenceRunner and
`arm.play_trajectory`; the human CLI exposes trajectory play and sequence run.
Use those implementations for recorded gestures, retaining hardware/calibration
provenance, entry-to-start validation, timing and cancellation checks.

The documented constrained MCP surface currently exposes saved poses, jogs,
gripper, sleep and stop, but not arbitrary recording/sequence replay. Plan an
explicit allowlisted broker replay capability if agent-facing replay is needed;
the Puppeteer MCP server must not bypass this restriction with the human CLI.
Preserve broker permission/profile/lease checks. An arm gesture is an optional
embodiment of an expressive intent; face and speech-motion capabilities may be
unsupported. Do not add automatic idle arm motion by analogy with Reachy.

## Work order

### Shared control contract

Packaging ownership: Puppeteer builds the optional StackChan, Reachy and SO-ARM
MCP server entry points from declared dependency extras and configuration. A clean
install must not require sibling source checkouts or a running Conversation App.
Keep the existing SO-ARM MCP/broker path interoperable rather than introducing a
second controller. SDK packages remain usable independently of Puppeteer/MCP.

Discovery uses explicit adapter providers: inspect installed SDK capability
metadata, runtime device/broker permissions and revision-pinned asset catalogs.
Reachy recorded behaviors come from `RecordedMoves.list_moves()` and their asset
metadata, not an emotion enum maintained by Puppeteer. StackChan reports its
actual firmware methods/features; its current SDK has no native emotion catalog.
SO-ARM combines its existing capability registry with pose/trajectory/sequence
libraries, filtered by the actual execution route's grants. Importing or listing
metadata must not open a hardware session or initiate movement.

Stable typed MCP tools accept discovered asset IDs; do not create one tool per
emotion or use arbitrary reflection to expose every SDK method. Explicit adapters
translate schemas and calls; auto-discovery does not imply that future SDK methods
are automatically safe, compatible or authorized. Build reproducible dependency
locks and asset manifests; refresh catalogs without hardcoding their contents.

Generalize action lifecycle and capability discovery while preserving typed,
device-specific control surfaces. Do not collapse all controls into motors or
recordings. Each device SDK should provide:

- Device identity, connection lifecycle, readiness, capabilities, limits, units
  and available feedback. Distinguish requested/commanded state from measured
  state and identify unavailable measurements.
- Typed native controls: Reachy head pose/antennas/body; SO-ARM joints,
  Cartesian/tool motion and gripper; StackChan yaw/pitch, eyes/mouth and built-in
  and external lights. Expose only supported validated operations.
- Validated timed assets and native playback where supported, with asset
  identity, version, calibration references, starting-state requirements and
  declared resource claims. Static poses, procedural actions and direct updates
  are also first-class operations.
- Action IDs and explicit accepted/running/completed/failed/cancelled semantics,
  deadline behavior, observable progress where supported, and device-specific
  cancellation/stop. Completion must describe what was verified; commanded target
  arrival is not automatically measured physical settling.
- A common execution owner for direct controls, playback and procedural updates.
  Validate overlap by actual device constraints: resource separation does not by
  itself prove concurrent execution is supported. Existing firmware can impose
  coarser serialization.
- Software-only fake transports/simulation for consumers, structured errors and
  stable CLI JSON output. Keep calibration, kinematics and guards device-owned.

Provide thin device MCP adapters using a common vocabulary for discovery,
state, action status, cancellation and catalog operations, plus typed native
tools for each embodiment. Keep the MCP transport independent from execution
logic. Prefer explicit schemas over an arbitrary motor-name/value command.
The SO-ARM adapter continues to call its existing broker and advertise only
granted operations; planned replay is not an existing agent capability.

Puppeteer supplies optional expressive recipes, procedural idle/talking behavior,
voice timing, cross-device coordination and semantic aliases. An optional
Puppeteer MCP server exposes those performances; direct SDK users still retain
native controls. An agent should not stream individual animation frames over MCP:
submit a bounded action or asset once and execute timing locally.

Examples of resource names (proposed, not current API): `head.pose`,
`antennas.left`, `antennas.right`, `arm.motion`, `gripper`, `face.eyes`,
`face.mouth`, `lights.builtin`, `lights.neohex`, `audio.output`.
Each adapter declares which resources actually exist and which can run together.
Allow partial expressive requests such as StackChan face-only changes without
inventing unspecified motor targets; native complete-keyframe requirements still
apply when selecting the native animation path.

1. Finish catalog and lifecycle design against the existing Puppeteer adapters.
2. Prove one pinned Reachy recorded emotion and its completion/cancellation path
   in software; verify audio-reactive motion ownership and custom extension path.
3. Develop the StackChan SDK facade and general CLI, with structured output and
   stable errors, backed by the same execution logic intended for MCP.
4. Author a small StackChan head-and-face example catalog and validate playback.
5. Add SO-ARM recorded gesture adapters and, separately, bounded broker replay.
6. Expose shared operations through optional MCP servers; integrate voice timing
   in Puppeteer and performance-script execution in Studio.
7. Package reproducible StackChan firmware plus prebuilt release artifacts.

Use software-only mocks for integration work. Physical acceptance is a separate,
explicitly authorized step. This plan changes no other repository's contracts.
