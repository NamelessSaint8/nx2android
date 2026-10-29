# Phase 1: API coverage

The app itself gains no external API in this phase. Two vendor services are used by the CI workflows only, through their own CLIs: Apple's notary service (`xcrun notarytool`, `stapler`) in `fork-release.yml`'s macOS job, and GitHub's REST API (`gh`) for the draft release and for checking runs during execution. The detector fired on "App Store Connect API key" in plan 01-08.

| capability | decision | reason |
|---|---|---|
| notarytool submit --wait (notarize the DMG, plan 01-08) | INTEGRATE | |
| notarytool log on a rejected submission (plan 01-08) | INTEGRATE | |
| stapler staple and stapler validate (plan 01-08) | INTEGRATE | |
| notarytool history and info | OPT-OUT | each run submits once and waits for its own verdict, so past submissions are never queried |
| notary webhook notifications | OPT-OUT | the job blocks on --wait; there is no server to receive a webhook |
| notarytool store-credentials keychain profiles | OPT-OUT | CI passes the API key file per run from the release environment; a stored profile would outlive the job |
| GitHub Releases: create a draft with four assets (gh release create, plan 01-08) | INTEGRATE | |
| GitHub Actions runs: list, watch, view logs (gh run, plans 01-07 and 01-08) | INTEGRATE | |
| GitHub Actions artifacts: count a run's artifacts (gh api, plan 01-08) | INTEGRATE | |
| GitHub environment secrets: list names (gh api, plan 01-08 checkpoint) | INTEGRATE | |
| GitHub release publish and edit | OPT-OUT | the developer publishes the draft by hand (CONTEXT, release trigger) |
| GitHub environment and secret creation from the session | OPT-OUT | the developer creates them so secret values never pass through an agent session (plan 01-08 Task 2) |
