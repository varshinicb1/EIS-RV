# Tech-stack upgrade notes

This file tracks what got bumped each phase, what's still pending, and
what to test before shipping.

---

## Phase 3 — major bumps (this session)

| Package | From | To | Notes |
|---|---|---|---|
| `electron` | `^28.0.0` | `^32.2.7` | Latest stable. Electron 28 went EOL April 2024. |
| `electron-builder` | `^24.9.1` | `^25.1.8` | Required by Electron 32. |
| `electron-store` | `^8.1.0` | `^8.2.0` | Stayed on the v8 (CJS) line; v9+ went ESM-only and `main.js` uses `require()`. |
| `electron-updater` | `^6.1.7` | `^6.3.9` | Latest v6. v7 changed signature semantics — defer until we wire real code-signing. |
| `react` / `react-dom` | `^18.3.1` | `^19.0.0` | React 19 stable. |
| `@types/react` / `@types/react-dom` | `^18.3.0` | `^19.0.0` | Type packages match the runtime. |
| `@react-three/fiber` | `^8.17.10` | `^9.1.0` | R3F 9 is the React-19-compatible line. R3F 8 cannot run on React 19. |
| `@react-three/drei` | `^9.117.0` | `^10.0.6` | Drei 10 is the matching peer for R3F 9. |
| `vite` | `^5.4.0` | `^6.0.6` | Vite 6 stable. Our `vite.config.js` doesn't use any removed APIs (verified). |
| `@vitejs/plugin-react` | `^4.3.0` | `^4.3.4` | Patch bump; works with both Vite 5 and 6. |
| `react-joyride` | `^2.9.3` | `^2.9.3` (kept) | 2.9.x declares peerDeps for React ≤18 only. We added an `overrides` block in `src/frontend/package.json` so npm accepts the install with React 19. The library has been reported to work on React 19 in practice; if you hit an issue, the `react-joyride@3.x` beta line is the upgrade path. |

### Static-scan results (no code changes needed for these)

| What we checked | Status |
|---|---|
| `forwardRef` / `useImperativeHandle` (deprecated wrapper in React 19; refs are now plain props) | **None used** — nothing to convert. |
| `ReactDOM.render` (removed since React 18) | **None used** — already on `createRoot`. |
| `@react-three/fiber` `<Canvas>` API | Used in 2 panels (`AlchemiPanel.jsx`, `BiosensorPanel.jsx`); the props we pass are unchanged in v9. |
| `react-joyride` import style | Already default-import (`import Joyride from 'react-joyride'`) — the v2 style. |
| Electron `webPreferences` defaults | Already secure: `contextIsolation: true`, `sandbox: true`, `nodeIntegration: false`, `webSecurity: true`. These match Electron 32's defaults. |
| Removed-in-Electron-14 options | `enableRemoteModule: false` was being set; **removed** (was a no-op since Electron 14, becomes a deprecation warning in 32+). |

### What still needs you to actually run

These are the verification steps. The package.json is correct, but
nothing replaces actually launching the desktop shell once.

```bash
# from project root
rm -rf node_modules package-lock.json
rm -rf src/frontend/node_modules src/frontend/package-lock.json

cd src/frontend
npm install
npm run build              # static build check first
cd ../..

npm install
npm run dev                # launch the desktop shell with --dev
```

Then click through every panel in the sidebar:

- [ ] Dashboard — telemetry mock should render (real-telemetry pass is Phase 4).
- [ ] EIS / CV / GCD / DRT / Battery / Supercap simulation panels — each runs against the local backend.
- [ ] Circuit Fitting — same.
- [ ] Biosensor — uses `<Canvas>` (R3F 9). Check the 3D view loads.
- [ ] Alchemi — uses `<Canvas>` and `useFrame`. Check the molecule animates.
- [ ] Literature Mining — talks to the local backend, hits the 2,421-paper DB.
- [ ] Validation panel.
- [ ] Reports panel.
- [ ] User Profile — license trial countdown should display correctly.
- [ ] Workspace / Materials / Joyride guided tour.

If a panel renders empty or throws, the most likely cause (in priority order):
1. A Lucide icon name changed between `1.14.x` (the broken old pin) and
   `0.469.x`. Look at the import error and pick the new name from
   <https://lucide.dev/icons>.
2. An R3F 9 prop renamed. Check the migration guide:
   <https://docs.pmnd.rs/react-three-fiber/api/canvas>.
3. A peer-dep mismatch warning that turned out to actually break.
   `npm install --legacy-peer-deps` will tolerate it; investigate
   afterwards.

---

## Phase 2.5 — earlier in-place fixes (kept for history)

| Package | Was | Now | Reason |
|---|---|---|---|
| `lucide-react` | `^1.14.0` | `^0.469.0` | The `1.x` family is a defunct 2022 prerelease line. Several icons referenced in components (e.g., `Wand2`, `BarChart2`) are not in `1.14.0`. |
| `jspdf` | `^4.2.1` | `^2.5.2` | `4.2.1` was not a real release. |
| `jspdf-autotable` | `^5.0.7` | `^3.8.4` | Same. |
| `react-joyride` | `^3.1.0` | `^2.9.3` | `3.x` was unstable; `2.9.x` is maintained. |

---

## Future bumps to plan

- **`next-themes`** (`^0.4.6`) — depends on Next.js but the app doesn't
  use Next. The hook works standalone but it's an awkward dependency.
  Consider replacing with the existing `useTheme.jsx` and removing the
  package.
- **`reactflow`** (`^11.11.4`) — has been renamed to `@xyflow/react`
  (v12). If diagram features are kept, plan a one-time migration.
- **`react-joyride` 2.x → 3.x**, once the 3.x line stabilises with React
  19 first-class support. We can then drop the `overrides` block.
- **`electron-store` 8 → 10** is a bigger move (ESM-only); pair it with
  converting `main.js` and `preload.js` to ESM.
- **`electron-updater` 6 → 7**, once we have real code-signing certs in
  CI. v7 enforces signature verification more strictly, which is what we
  want when we actually ship updates.
