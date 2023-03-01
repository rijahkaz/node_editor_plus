# Use this at your own risk, this is still pretty much experimental. It might occasionaly crash your Maya so please save frequently.

To install, copy the "node_editor_plus" folder to your Maya scripts dir.
After that, copy and run these lines of code in a Python command tab in Maya's script editor (you can also add this to a python shelf button):
```
from node_editor_plus import node_editor_plus
from node_editor_plus import node_connection_filter
from node_editor_plus import custom_nodes
from node_editor_plus import overrides
nep = node_editor_plus.NodeEditorPlus()
nep.ui()
```

Note: the folder to be copied is the one with a "__init__.py" inside

## Hit "C" with some nodes selected to create comments. Press "F2" with the nodes selected to rename them. Press "B" with a comment selected to change the comment color. 


Command List:
C: Create Comment
F2: Rename Comment
B: Change Comment Color
Ctrl/Command + I: Pick New Image
Ctrl/Command + F: Show Search Menu
I: Graph Input
O: Graph Output
Alt + Shift + W: Align Middle
Alt + Shift + S: Align Center
Shift + W: Align Top
Shift + S: Align Bottom
Shift + A: Align Left
Shift + D: Align Right
Shift + H: Distribute Horizontal
Shift + V: Distribute Vertical
