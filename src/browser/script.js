const q = sel => document.querySelector(sel)
const qa = sel => [...document.querySelectorAll(sel)]

const DATA = window.DATA
const FILE_PATH = window.FILE_PATH
const MAX_LEVEL = window.MAX_LEVEL

const FOLD_KEY = "fold:" + FILE_PATH
const LEVEL_KEY = "level:" + FILE_PATH

const root = q("#comments")
const slider = q("#level-slider")
const valLabel = q("#level-val")

let foldState = {}

function renderMath(container) {
    renderMathInElement(container, {
        delimiters: [
            { left: "$$", right: "$$", display: true },
            { left: "$", right: "$", display: false },
        ],
        throwOnError: false,
    })
}

function toVscodePath(p) {
    p = p.replace(/\\\\/g, "/")
    if (/^[A-Za-z]:/.test(p)) {
        p = "/" + p[0].toLowerCase() + p.slice(1)
    }
    return p
}

function openInVscode(line) {
    const url = "vscode://file" + toVscodePath(FILE_PATH) + ":" + line
    console.log("opening:", url)
    window.location.href = url
}

function saveFoldState() {
    try {
        localStorage.setItem(FOLD_KEY, JSON.stringify(foldState))
    } catch (e) {}
}

function saveLevel() {
    try {
        localStorage.setItem(LEVEL_KEY, String(currentMinLevel))
    } catch (e) {}
}

function nodeKey(item) {
    return "L" + item.line + ":i" + item.indent
}

// ---- Visibility: node visible iff effective_level >= currentMinLevel ----
function nodeVisible(item) {
    return item.effective_level >= currentMinLevel
}

function visibleChildren(item) {
    return item.children.filter(nodeVisible)
}

function visibleDescendants(item) {
    let n = 0
    for (const c of item.children) {
        if (!nodeVisible(c)) continue
        n += 1 + visibleDescendants(c)
    }
    return n
}

function renderNode(item) {
    const key = nodeKey(item)
    const kids = visibleChildren(item)
    const hasVisibleChildren = kids.length > 0

    const node = document.createElement("div")
    node.className = "node"
    node.dataset.key = key
    node.dataset.eff = String(item.effective_level)

    const row = document.createElement("div")
    row.className = "row"
    row.title = item.raw_line.split("#.")[0] + "(L" + item.line + ")"
    row.addEventListener("click", () => openInVscode(item.line))

    const caret = document.createElement("span")
    caret.className = "caret" + (hasVisibleChildren ? " clickable" : "")
    if (hasVisibleChildren) {
        caret.addEventListener("click", e => {
            e.stopPropagation()
            const collapsed = node.classList.toggle("collapsed")
            foldState[key] = collapsed
            saveFoldState()
            updateCaret(caret, node, item)
        })
    }

    const body = document.createElement("div")
    body.className = "body"

    const lineno = document.createElement("span")
    lineno.className = "lineno"
    lineno.textContent = "L" + item.line
    body.appendChild(lineno)

    const md = document.createElement("span")
    md.innerHTML = marked.parse(item.comment, { breaks: false, gfm: true })
    body.appendChild(md)

    if (item.level > 0) {
        const pill = document.createElement("span")
        pill.className = "levelpill"
        pill.textContent = "L" + item.level
        body.appendChild(pill)
    }

    renderMath(body)

    row.appendChild(caret)
    row.appendChild(body)
    node.appendChild(row)

    if (hasVisibleChildren) {
        const kidsEl = document.createElement("div")
        kidsEl.className = "children"
        for (const child of kids) {
            kidsEl.appendChild(renderNode(child))
        }
        node.appendChild(kidsEl)

        if (foldState[key] === true) node.classList.add("collapsed")
        updateCaret(caret, node, item)
    } else {
        caret.textContent = ""
    }

    return node
}

function updateCaret(caret, node, item) {
    const collapsed = node.classList.contains("collapsed")
    if (collapsed) {
        const n = visibleDescendants(item)
        caret.innerHTML = "&#9654;<span class='badge'>" + n + "</span>"
    } else {
        caret.textContent = "\u25BC"
    }
}

function renderAll() {
    root.innerHTML = ""
    for (const item of DATA) {
        if (!nodeVisible(item)) continue
        root.appendChild(renderNode(item))
    }
    updateFooter()
}

function updateFooter() {
    let hidden = 0
    let total = 0
    ;(function walk(nodes) {
        for (const n of nodes) {
            total += 1
            if (!nodeVisible(n)) hidden += 1
            walk(n.children)
        }
    })(DATA)

    const footer = q("#footer")
    if (hidden === 0) {
        footer.textContent = total + " comment(s) shown."
    } else {
        footer.textContent = hidden + " of " + total + " comment(s) hidden (below min level). Lower the slider to reveal."
    }
}

function setAllCollapsed(collapsed) {
    qa("#comments .node[data-key]").forEach(node => {
        if (!node.querySelector(":scope > .children")) return
        node.classList.toggle("collapsed", collapsed)

        const caret = node.querySelector(":scope > .row > .caret")
        if (collapsed) {
            const kidCount = node.querySelectorAll(":scope > .children .node").length
            caret.innerHTML = "&#9654;<span class='badge'>" + kidCount + "</span>"
        } else {
            caret.textContent = "\u25BC"
        }

        foldState[node.dataset.key] = collapsed
    })
    saveFoldState()
}

// -----------------------

slider.value = String(currentMinLevel)
valLabel.textContent = "\u2265 " + currentMinLevel

slider.addEventListener("input", () => {
    currentMinLevel = parseInt(slider.value, 10)
    valLabel.textContent = "\u2265 " + currentMinLevel
    saveLevel()
    renderAll()
})

try {
    foldState = JSON.parse(localStorage.getItem(FOLD_KEY) || "{}")
} catch (e) {
    foldState = {}
}

// Slider = MINIMUM level to show. 0 means "show everything".
let currentMinLevel = 0
const savedMin = parseInt(localStorage.getItem(LEVEL_KEY) || "", 10)
if (!Number.isNaN(savedMin) && savedMin >= 0 && savedMin <= MAX_LEVEL) {
    currentMinLevel = savedMin
}

q("#collapse-all").addEventListener("click", () => setAllCollapsed(true))
q("#expand-all").addEventListener("click", () => setAllCollapsed(false))

renderAll()
