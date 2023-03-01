# Use this at your own risk, this is still pretty much experimental. It might occasionaly crash your Maya so please save frequently.

To install, copy the "node_editor_plus" folder to your Maya scripts dir. (**Note**: the folder to be copied is the one with a "\__init\__.py" inside)
After that, copy and run these lines of code in a Python command tab in Maya's script editor:
```
from node_editor_plus import node_editor_plus
nep = node_editor_plus.NodeEditorPlus()
nep.ui()
```
## Add this command to a python shelf button, if you use it, it is **NOT** recommended to alternate between the original Node Editor and Node Editor Plus, you may experience crashing or lose NEP data.

-

## Quickstart:
Hit "C" with some nodes selected to create comments. Press "B" with a comment selected to change the comment color. 


## Command List:
### Custom Node Creation
+ C: Create Comment
+ F2: Rename Comment
+ B: Change Comment Color
+ Ctrl/Command + I: Pick New Image
+ Ctrl/Command + F: Show Search Menu

### Extended graphing capability: hover an attribute in the Node and press to graph
+ I: Graph Input
+ O: Graph Output

### Aligning functions - these also work with native nodes
+ Alt + Shift + W: Align Middle
+ Alt + Shift + S: Align Center
+ Shift + W: Align Top
+ Shift + S: Align Bottom
+ Shift + A: Align Left
+ Shift + D: Align Right
+ Shift + H: Distribute Horizontal
+ Shift + V: Distribute Vertical