function ladder() {
    const MAX_LEVEL = window.MAX_LEVEL
    const FILE_PATH = window.FILE_PATH
    const DATA = window.DATA

    // Precompute stable keys once
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
            // Nothing persisted — everything resets on load.
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
            this.foldState[item.key] = !(this.foldState[item.key] === true)
        },

        setAllCollapsed(collapsed) {
            const walk = items => {
                for (const i of items) {
                    if (i.children.length > 0) this.foldState[i.key] = collapsed
                    walk(i.children)
                }
            }
            walk(DATA)
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

        // Renders the subtree of `item` as HTML (depth >= 2).
        // Alpine x-for doesn't recurse well, so we hand-build deeper levels.
        subtreeHtml(item) {
            const html = this.childrenToHtml(item)
            this.$nextTick(() => this.renderMathIn(item))
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
                const title = child.raw_line.split("#.")[0].replace(/"/g, "&quot;")
                out += `
                    <div class="node" data-key="${child.key}" data-eff="${child.effective_level}" ${collapsed ? 'data-collapsed="1"' : ""}>
                        <div class="row" title="${title}(L${child.line})" data-open-line="${child.line}">
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

        renderMathIn(el) {
            if (!el || !window.renderMathInElement) return
            window.renderMathInElement(el, {
                delimiters: [
                    { left: "$$", right: "$$", display: true },
                    { left: "$", right: "$", display: false },
                ],
                throwOnError: false,
            })
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

// Delegate clicks inside hand-rendered subtrees (depth >= 2).
document.addEventListener("click", e => {
    const caret = e.target.closest("[data-toggle-key]")
    if (caret) {
        e.stopPropagation()
        const node = caret.closest(".node")
        const children = node.querySelector(":scope > .children")
        const key = caret.dataset.toggleKey
        const root = document.querySelector("[x-data]")
        const state = Alpine.$data(root)

        const nowCollapsed = !node.classList.contains("collapsed")
        node.classList.toggle("collapsed", nowCollapsed)
        state.foldState[key] = nowCollapsed

        // Update caret icon
        if (nowCollapsed) {
            const count = children ? children.querySelectorAll(".node").length : 0
            caret.innerHTML = "&#9654;<span class='badge'>" + count + "</span>"
        } else {
            caret.textContent = "\u25BC"
        }
        if (children) children.style.display = nowCollapsed ? "none" : ""
        return
    }

    const row = e.target.closest("[data-open-line]")
    if (row) {
        const line = parseInt(row.dataset.openLine, 10)
        const root = document.querySelector("[x-data]")
        Alpine.$data(root).openInVscode(line)
    }
})

// Re-run KaTeX after Alpine renders.
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
    if (root) observer.observe(root, { childList: true, subtree: true })
})
