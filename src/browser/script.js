function ladder() {
    const MAX_LEVEL = window.MAX_LEVEL
    const FILE_PATH = window.FILE_PATH
    const DATA = window.DATA
    const FOLD_KEY = "fold:" + FILE_PATH
    const LEVEL_KEY = "level:" + FILE_PATH

    // Precompute keys once
    function assignKeys(items) {
        for (const item of items) {
            item.key = "L" + item.line + ":i" + item.indent
            assignKeys(item.children)
        }
    }
    assignKeys(DATA)

    return {
        MAX_LEVEL,
        minLevel: 0,
        foldState: {},

        init() {
            try {
                this.foldState = JSON.parse(localStorage.getItem(FOLD_KEY) || "{}")
            } catch (e) {
                this.foldState = {}
            }
            const saved = parseInt(localStorage.getItem(LEVEL_KEY) || "", 10)
            if (!Number.isNaN(saved) && saved >= 0 && saved <= MAX_LEVEL) {
                this.minLevel = saved
            }
        },

        get totalCount() {
            let n = 0
            const walk = items => {
                for (const i of items) {
                    n++
                    walk(i.children)
                }
            }
            walk(DATA)
            return n
        },

        get visibleRoots() {
            return DATA.filter(i => this.nodeVisible(i))
        },

        get footerText() {
            let hidden = 0
            let total = 0
            const walk = items => {
                for (const n of items) {
                    total++
                    if (!this.nodeVisible(n)) hidden++
                    walk(n.children)
                }
            }
            walk(DATA)
            return hidden === 0 ? total + " comment(s) shown." : hidden + " of " + total + " comment(s) hidden (below min level). Lower the slider to reveal."
        },

        nodeVisible(item) {
            return item.effective_level >= this.minLevel
        },

        visibleChildren(item) {
            return item.children.filter(c => this.nodeVisible(c))
        },

        visibleDescendants(item) {
            let n = 0
            for (const c of item.children) {
                if (!this.nodeVisible(c)) continue
                n += 1 + this.visibleDescendants(c)
            }
            return n
        },

        isCollapsed(item) {
            return this.foldState[item.key] === true
        },

        toggle(item) {
            const k = item.key
            const next = !(this.foldState[k] === true)
            this.foldState[k] = next
            try {
                localStorage.setItem(FOLD_KEY, JSON.stringify(this.foldState))
            } catch (e) {}
        },

        setAllCollapsed(collapsed) {
            const walk = items => {
                for (const i of items) {
                    if (i.children.length > 0) this.foldState[i.key] = collapsed
                    walk(i.children)
                }
            }
            walk(DATA)
            try {
                localStorage.setItem(FOLD_KEY, JSON.stringify(this.foldState))
            } catch (e) {}
        },

        saveLevel() {
            try {
                localStorage.setItem(LEVEL_KEY, String(this.minLevel))
            } catch (e) {}
        },

        caretHtml(item) {
            const kids = this.visibleChildren(item)
            if (kids.length === 0) return ""
            if (this.isCollapsed(item)) {
                return "&#9654;<span class='badge'>" + this.visibleDescendants(item) + "</span>"
            }
            return "\u25BC"
        },

        renderMarkdown(text) {
            return marked.parse(text, { breaks: false, gfm: true })
        },

        // Escape hatch for arbitrary depth rendering.
        // x-for recursion in Alpine is awkward beyond a few levels,
        // so we hand-render deep subtrees and re-run math afterwards.
        deepChildrenHtml(item) {
            const html = this.childrenToHtml(item)
            this.$nextTick(() => {
                const root = document.querySelector(`[data-key="${item.key}"] .children`)
                if (root && window.renderMathInElement) {
                    window.renderMathInElement(root, {
                        delimiters: [
                            { left: "$$", right: "$$", display: true },
                            { left: "$", right: "$", display: false },
                        ],
                        throwOnError: false,
                    })
                }
            })
            return html
        },

        childrenToHtml(item) {
            const kids = this.visibleChildren(item)
            if (kids.length === 0) return ""
            let out = ""
            for (const child of kids) {
                const collapsed = this.isCollapsed(child)
                const hasKids = this.visibleChildren(child).length > 0
                const caret = hasKids ? (collapsed ? "&#9654;<span class='badge'>" + this.visibleDescendants(child) + "</span>" : "\u25BC") : ""
                const pill = child.level > 0 ? `<span class="levelpill">L${child.level}</span>` : ""
                out += `
                    <div class="node" data-key="${child.key}" data-eff="${child.effective_level}" ${collapsed ? 'data-collapsed="1"' : ""}>
                        <div class="row" title="${child.raw_line.split("#.")[0].replace(/"/g, "&quot;")}(L${child.line})">
                            <span class="caret ${hasKids ? "clickable" : ""}" data-toggle-key="${child.key}">${caret}</span>
                            <div class="body">
                                <span class="lineno">L${child.line}</span>
                                <span>${this.renderMarkdown(child.comment)}</span>
                                ${pill}
                            </div>
                        </div>
                        ${hasKids ? `<div class="children" ${collapsed ? 'style="display:none"' : ""}>${this.childrenToHtml(child)}</div>` : ""}
                    </div>`
            }
            return out
        },

        // ---- VS Code ----
        toVscodePath(p) {
            p = p.replace(/\\\\/g, "/")
            if (/^[A-Za-z]:/.test(p)) {
                p = "/" + p[0].toLowerCase() + p.slice(1)
            }
            return p
        },

        openInVscode(line) {
            const url = "vscode://file" + this.toVscodePath(FILE_PATH) + ":" + line
            console.log("opening:", url)
            window.location.href = url
        },
    }
}

// Re-render KaTeX whenever Alpine updates the tree.
document.addEventListener("alpine:initialized", () => {
    const observer = new MutationObserver(() => {
        const root = document.getElementById("comments")
        if (root && window.renderMathInElement) {
            window.renderMathInElement(root, {
                delimiters: [
                    { left: "$$", right: "$$", display: true },
                    { left: "$", right: "$", display: false },
                ],
                throwOnError: false,
            })
        }
    })
    const root = document.getElementById("comments")
    if (root) {
        observer.observe(root, { childList: true, subtree: true })
    }
})
