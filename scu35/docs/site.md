# Hosted lesson and presenter

- Self-paced lesson: https://aew2015.github.io/amd_examples/
- Presenter: https://aew2015.github.io/amd_examples/presenter.html
- Editable content: `docs/presenter/index.html`, `style.css` and `app.js`.
- Lesson adaptation and chapter progress: `scripts/build_site.py`.

Both views contain recorded hardware evidence. The browser never programs the board. Chapter completion is stored only in the visitor's browser; no analytics or account is required. GitHub Pages serves the static pages; the linked source and notebooks live on `scu35-pmc-lab`.

Chapter 18, **Complete example: Ethernet crypto** (`#ethernet`), brings the IPI design, MicroBlaze V firmware, reference PDI/ELF/XSA, notebook, local dashboard, measured packet results and reproduction commands together. Its screenshots and LMS/HSS plots are recorded evidence. The live dashboard runs locally with a connected SCU35; Pages does not host a board connection. The AXI Ethernet/AXI DMA architecture is described as a separate unbuilt follow-on.

Chapter 19, **Notebook walkthroughs** (`#notebooks`), explains each of the 11 PMC
notebooks plus the separate Ethernet notebook and links directly to the files on
the source branch. It describes live flags, embedded firmware, saved-output
provenance, repeat measurements and timing limits. Published notebooks retain
executed outputs with an execution note; hardware defaults stay disabled for
the next visitor. The site links to these saved results and never runs a kernel.

To regenerate from this directory with the documented Python environment:

```text
python scripts/refresh_presenter.py
python scripts/build_site.py
python scripts/check_site.py
```

The build produces `out/site/`, which is deliberately ignored in the source branch. It embeds the existing images and client code, resolves source/notebook links to GitHub, and includes the four linked evidence reports as rendered pages. There are no vendor tools, signing keys, local configuration files, or hardware services in the web deployment.

Pages is configured to serve the root of the `gh-pages` branch. To publish an update, build and check the site, then copy **only the contents of `out/site/`** into a separate checkout of `gh-pages`, commit, and push. Do not copy the entire lab into the deployment branch. After changing any lab source, regenerate `manifest.json` with `python scripts/make_manifest.py` and run `python lab.py verify` before committing the source branch.

Optional browser verification (requires Playwright and an installed browser): serve `out/site/` locally and run `python scripts/check_site.py --url http://localhost:8000/index.html`. Set `SCU35_BROWSER` to a browser executable if needed. The checker exercises all chapters, completion persistence/reset, boot selectors, image loading, the mobile layout and the original presenter.
