# Maintainer publishing checklist / 公開手順

This package is a prepared repository tree, not an already-created GitHub repository. Confirm the actual copyright holder(s) and authorization to publish the code/documentation under MIT; the notice currently uses the collective project label “AFP Lab contributors” rather than assigning ownership to an individual or company without instruction. Verify source/data rights and no private content. Do not upload local field files or cache. Use the synthetic screenshot for public demonstrations until real results are cleared for publication.

1. Extract into a fresh folder, open the `afp-lab` directory, run `python -m unittest -v` and `python -m afp_lab.lab --out experiments/demo`.
2. Create an **empty** GitHub repository named `afp-lab` under the chosen account/organization; do not auto-generate a README or license. Private staging is also possible. No account or remote URL is assumed by this package.
3. From the repository root:

```sh
git init -b main
git add .
git status --short
git diff --cached --stat
```

Inspect the staged content and rights. Only then:

```sh
git commit -m "Publish AFP Lab v0.7 research baseline"
git tag -a v0.7.0 -m "AFP Lab research baseline v0.7"
git remote add origin <YOUR_REPOSITORY_URL>
git push -u origin main
git push origin v0.7.0
```

Replace the placeholder URL with the actual empty repository URL (do not paste literal angle brackets into a shell). A Git user identity may be required; use the account's appropriate public attribution. The tag is proposed, not already created. Do not manufacture historical commits. The design narrative and archived notes describe the earlier development.

4. Check the Actions run, README rendering and all seven Mermaid diagrams in each language. The proposed workflow tests Python 3.10 and 3.13 on Windows, macOS and Linux. No hosted CI execution is claimed yet.
5. Enable GitHub Discussions if desired; use Issues for specific reproducible problems. Create a v0.7.0 Release from the tag if helpful. Link the repository from the activity homepage and the homepage from the repository (already in README).
6. Adapt [community drafts](community.md) with the actual URL. Start the discussion with a question, not an assertion of a product defect. Do not use a private field screenshot.

Suggested repository description: `Experimental platform for local sensor networks, LoRa protocol research and terrain-aware radio coverage.`

Suggested topics: `lora`, `m5stack`, `e220`, `iot`, `sensor-network`, `radio-propagation`, `simulation`, `field-research`, `python`.
