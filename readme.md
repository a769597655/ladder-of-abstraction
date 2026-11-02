Extract `#.` comments from a Python source file and render them as an indented HTML outline with markdown, inline code, and KaTeX support.

Clicking a comment opens the source file at that line in VS Code. 
Comments nest by indentation and can be folded/unfolded.

Importance levels:  
- `#.` = level 0 (default, least important)
- `#.n` = level n

Whitespace after `#.` is allowed: `#.1 foo` and `#. 1 foo` both parse as level 1 with comment "foo".

A slider at the top sets the MINIMUM level to show:
- slider 0 -> show everything
- slider 1 -> hide level-0 comments
- slider 2 -> hide level-0 and level-1 comments

Effective level rule (parent derives importance from children):
    effective(node) = max(own_level, max(effective(child) for child in children))

> A parent is only hidden once its ENTIRE subtree is below the slider. A parent stays visible as long as any visible descendant remains. So a level-0 parent with a level-2 child becomes effectively level 2, and hides together with that child when the slider hits 2.

# Usage
## Dev

```sh
watchexec -i ./src -e py,html,js,css -r "python3-64.exe .\src\cli\main.py .\test\face.py"
```

## Serve
and then open the `.html` file 
or 
```sh
npm i http-server
http-server -c-1 ./path/to/dir/
```