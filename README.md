    # SigmaOS-file-writer

    Minimal distraction-free text writer

    Part of the **SigmaOS** sovereign operating-system ecosystem — a multi-repository
    distribution modelled on Linux Mint and Omarchy Linux. See the parent
    [`SigmaOS`](https://github.com/AaryanSinghChauhan09/SigmaOS) repository for the
    full component index.

    ## Upstream inspirations
    - https://github.com/omacom/omawrite

    ## Design principles applied
    - **KISS**
- **Least Astonishment**
- **Fail-Fast**
- **Separation of Concerns**
- **Defensive Programming**
- **Deterministic Testing**

    ## Usage
    Verbs: `open, write, focus-stats, autosave-plan`

    ```
    $ sigma-writer open notes.txt
$ sigma-writer write notes.txt --text "hello world"
$ sigma-writer focus-stats --text "one two three"
words=3 chars=13 paragraphs=1 reading_minutes=1
$ sigma-writer autosave-plan --interval 60 --now 1000 --dirty

    ```

    ## Build & test
    ```
    make build
    make test
    ```

    ## Licence
    GNU General Public License v3.0 (FOSS).
