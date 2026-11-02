function assignKeys(items) {
    for (const i of items) {
        i.key = "L" + i.line + ":i" + i.indent
        assignKeys(i.children)
    }
}
assignKeys(window.DATA)


function app() {
    return {
        MAX_LEVEL: window.MAX_LEVEL,
        FILE_PATH: window.FILE_PATH,
        DATA: window.DATA,
        minLevel: 0,

        init() {
        },

        get totalCount() {
            let n = 0
            const walk = items => {
                for (const i of items) {
                    n++
                    walk(i.children)
                }
            }
            walk(this.DATA)
            return n
        },

        get visibleRoots() {
            return this.DATA.filter(i => i.effective_level >= this.minLevel)
        },

        get footerText() {
            let hidden = 0,
                total = 0
            const walk = items => {
                for (const n of items) {
                    total++
                    if (n.effective_level < this.minLevel) hidden++
                    walk(n.children)
                }
            }
            walk(this.DATA)
            return hidden === 0 ? total + " comment(s) shown." : hidden + " of " + total + " comment(s) hidden (below min level). Lower the slider to reveal."
        },

        visible(item) {
            return item.effective_level >= this.minLevel
        },

        setAllCollapsed(collapsed) {
            // Every node component listens to this flag.
            this.$dispatch("set-collapsed", { collapsed })
        },

        open(line) {
            let p = window.FILE_PATH.replace(/\\\\/g, "/")
            if (/^[A-Za-z]:/.test(p)) p = "/" + p[0].toLowerCase() + p.slice(1)
            window.location.href = "vscode://file" + p + ":" + line
        },
    }
}

function node(item, root) {
    return {
        item,
        root,
        collapsed: false,
        get kids() {
            return item.children.filter(c => c.effective_level >= root.minLevel)
        },
        get caretHtml() {
            if (!this.kids.length) return ""
            if (this.collapsed) return "&#9654;<span class='badge'>" + this.countDescendants() + "</span>"
            return "\u25BC"
        },
        countDescendants() {
            let n = 0
            const walk = items => {
                for (const c of items) {
                    if (c.effective_level < root.minLevel) continue
                    n++
                    walk(c.children)
                }
            }
            walk(item.children)
            return n
        },
        init() {
            this.$el.innerHTML = document.getElementById("node-template").innerHTML
            Alpine.initTree(this.$el)

            // Global collapse-all listener
            this.$root.addEventListener("set-collapsed", e => {
                if (this.kids.length) this.collapsed = e.detail.collapsed
            })
        },
    }
}
