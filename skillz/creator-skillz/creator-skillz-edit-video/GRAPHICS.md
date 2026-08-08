# Motion graphics and B-roll

How a graphic proposed in Plan becomes a rendered clip in `edit/<n>/graphics/`. Reached from Produce, step 3. Segments with no approved graphic skip this entirely.

## Build one at a time

Start a graphic only after the previous one has rendered and been verified. `video-use`'s Hard Rule 10 calls for parallel sub-agents; its process does not apply here. Serial builds keep each graphic's style consistent with the one before it, and let a palette or timing correction made on graphic 2 carry into graphic 3 instead of landing after all of them are already wrong.

## The slot

One folder per graphic, named for what it shows rather than its index:

```
edit/<n>/graphics/<slot-name>/
├── brief.md          the spec, written before anything is built
├── index.html        the HyperFrames composition
└── render.mp4        or render.webm when it needs alpha
```

`brief.md` carries what a re-render three gates later would otherwise have to reinvent:

```markdown
# <slot-name>

- **Shows:** one sentence
- **Lands on:** the payoff word, and its timestamp in the segment's cut timeline
- **Duration:** seconds, and why
- **Placement:** full-frame cut-away, or overlay with alpha
- **Palette and type:** the concrete values used
- **Rejected:** approaches tried and dropped, with the reason
```

## Build

Read `hyperframes` first — it is the mandatory entry point and routes to the workflow that fits. `hyperframes-core` has the composition contract, `hyperframes-animation` the motion rules.

```bash
cd edit/<n>/graphics/<slot-name>
npx --yes hyperframes init . --example blank --non-interactive --skip-skills
# author index.html
npx --yes hyperframes lint          # fast loop while building
npx --yes hyperframes check         # gate before rendering
npx --yes hyperframes render . --quality high -o render.mp4
```

Render `--format webm -o render.webm` instead when the graphic sits over footage and needs transparency. A full-frame cut-away that replaces the footage does not.

## Timing

- **Land the payoff on the word.** Take the payoff word's timestamp from the cut transcript and start the graphic its reveal duration earlier, so the finished frame arrives as the word is spoken.
- **Readable at 1x.** Roughly 3 seconds floor, 5–7 for a simple card, 8–14 for a dense diagram.
- **Hold the final frame** for at least a second before the cut.
- **One reveal at a time.** Two new elements appearing together is one the viewer misses.

## Verify and wire in

`ffprobe` every render for duration and dimensions before moving on — a graphic that came out a second short silently desyncs its overlay window.

Then add it to the segment's cut list as an entry in `overlays`, with `file` pointing at the actual rendered path, `start_in_output` on the cut timeline, and `duration` matching what `ffprobe` reported.
