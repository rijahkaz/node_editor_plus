# Use this at your own risk, this is still pretty much experimental

To install, copy the "node_editor_plus" folder to your Maya scripts dir.
After that, copy and run these lines of code in a Python command tab in Maya's script editor (you can also add this to a python shelf button):
```
from node_editor_plus import node_editor_plus
nep = node_editor_plus.NodeEditorPlus()
nep.ui()
```

Note: the folder to be copied is the one with a "__init__.py" inside

## Hit "C" with some nodes selected to create comments. Press "F2" with the nodes selected to rename them. Press "B" with a comment selected to change the comment color.