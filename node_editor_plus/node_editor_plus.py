import os
from maya import mel, cmds, OpenMayaUI
from shiboken2 import wrapInstance
from PySide2.QtWidgets import *
from PySide2.QtGui import *
from PySide2.QtCore import *
from node_editor_plus import custom_nodes

# version tracking
VERSION = "0.1.5"

# constants
WINDOW_NAME = "NodeEditorPlusWindow"
DEFAULT_HUD_MESSAGE = "Press Tab to create a node"

def getCurrentScene(node_editor):
    ctrl = OpenMayaUI.MQtUtil.findControl(node_editor)
    if ctrl is None:
        raise RuntimeError("Node editor is not open")
    nodeEdPane = wrapInstance(int(ctrl), QWidget)
    stack = nodeEdPane.findChild(QStackedLayout)
    graph_view = stack.currentWidget().findChild(QGraphicsView)
    scene = graph_view.scene()
    return scene

def getCurrentView(node_editor):
    scene = getCurrentScene(node_editor)
    return scene.views()[0]


class AlignNodes():
    def __init__(self):
        pass

    def getFullLength(self, axis, graphicsList):
        fullLength = 0
        for node in graphicsList:
            if axis == "x":
                fullLength = fullLength + node.boundingRect().width()
            elif axis == "y":
                fullLength = fullLength + node.boundingRect().height()
    
        return fullLength

    def getInitialNodeValue(self, axis, graphicsList):
        initialValue = 0
        firstNode = graphicsList[0]
        if axis == "x":
            initialValue = firstNode.pos().x()
        elif axis == "y":
            initialValue = firstNode.pos().y()
    
        return initialValue
    
    def horizontalAlign(self, graphicsList):
        xValue = 0
        yValue = 0
        #Get Y Value: Will be the same for all.
        yValue = self.getInitialNodeValue("y", graphicsList)
        #Get full length of nodes selected.
        fLen = self.getFullLength("x", graphicsList)
        #Get gap between Nodes.
        spaceBetween = fLen / len(graphicsList) - 1
        #Get X position for the first node.
        xValue = self.getInitialNodeValue("x", graphicsList)
        #Ititate through list and asign values.
        for node in graphicsList:
            node.setPos(xValue, yValue)
            #Here I add the width because I want a wider gap between them horizontal
            xValue += node.boundingRect().width() + spaceBetween 
    def verticalAlign(self, graphicsList):
        xValue = 0
        yValue = 0
        #Get X Value: Will be the same for all.
        xValue = self.getInitialNodeValue("x", graphicsList)
        #Get full length of nodes selected.
        fLen = self.getFullLength("y", graphicsList)
        #Get gap between Nodes.
        spaceBetween = fLen / len(graphicsList) - 1
        #Get Y position for the first node.
        yValue = self.getInitialNodeValue("y", graphicsList)
        for node in graphicsList:
            node.setPos(xValue, yValue)
            #Here I did not add the height because they would be too far apart.
            yValue += spaceBetween
       

class NodeEditorPlus():
    node_editor = None
    icons_path = ""

    def __init__(self):
        self.icons_path = os.path.join(os.path.dirname(__file__), "icons")

    def tab_change_callback(self):
        # intercept for our needs then call original callback
        parent   = cmds.setParent(query=True)
        showMenu = None # this doesn't seem it's being used at all in the function
        mel.eval("nodeEdUpdateUIByTab \"{}\" \"{}\"".format(self.node_editor, showMenu))

    def settings_changed_callback(self, *args):
        # intercept for our needs then call original callback
        #print(cmds.nodeEditor(self.node_editor, query=True, stateString=True))
        mel.eval("nodeEdSyncControls \"{}\"".format(args[0]))

    def close_all_node_editors(self):
        # makes sure only our Node Editor Plus window is shown otherwise Tabs break
        windows_list = cmds.lsUI(windows=True)
        for window in windows_list:
            if "nodeEditorPanel" in window:
                cmds.deleteUI(window)
        if cmds.window(WINDOW_NAME, exists=True):
            cmds.deleteUI(WINDOW_NAME)

    def ui(self):
        self.close_all_node_editors()

        cmds.window(WINDOW_NAME, title="Node Editor Plus v{}".format(VERSION), widthHeight=(800, 550) )
        form = cmds.formLayout()
        p = cmds.scriptedPanel(type="nodeEditorPanel")
        self.node_editor = p+"NodeEditorEd"
        cmds.formLayout(form, edit=True, attachForm=[(p,s,0) for s in ("top","bottom","left","right")])

        # our upgrade to the Node Editor :3
        self.create_sidebar()

        # this never worked, I'm disabling it
        cmds.nodeEditor(self.node_editor, edit=True, allowTabTearoff=False)
        # intercept hotkeys for our functionality
        cmds.nodeEditor(self.node_editor, edit=True, keyPressCommand=self.comment_key_callback)
        # in case we need to intercept these too, but atm it's not doing anything (v0.1.4)
        cmds.nodeEditor(self.node_editor, edit=True, tabChangeCommand=self.tab_change_callback)
        # intercept original callbacks, there are important so we can apply grid snapping for example
        cmds.nodeEditor(self.node_editor, edit=True, settingsChangedCallback=self.settings_changed_callback)

        cmds.showWindow(WINDOW_NAME)

        

    def comment_key_callback(self, *args):
        ''' Detects keypresses'''
        node_editor = args[0]
        key_pressed = args[1]

        print(key_pressed)

        mods = cmds.getModifiers()
        # create comment on selected nodes
        if key_pressed == "C":
            self.create_comment()
            return True
        # rename selected comment
        elif key_pressed == "F2":
            self.rename_comment()
            return True
        # change background color for selected comment(s)
        elif key_pressed == "B":
            self.color_comment()
            return True
        # delete selected comment(s)
        elif key_pressed == "Del" or key_pressed == "Backspace": 
            self.delete_comment()
        # align selected node(s) horizontally
        elif (mods & 1) > 0 and key_pressed == "A": 
            self.align_nodes("horizontal")
            return True
        # align selected node(s) vertically
        elif (mods & 1) > 0 and key_pressed == "V": 
           self.align_nodes("vertical")
           return True

        # remake of original hotkeys to make them work with our custom nodes
        # ToDo: make them calculate our nodes to frame 
        elif key_pressed == "A":
            cmds.nodeEditor(node_editor, edit=True, frameAll=True)
            return True
        elif key_pressed == "F":
            cmds.nodeEditor(node_editor, edit=True, frameSelected=True)
            return True

        # in the end if we didn't intercept a key, run original callback
        mel.eval("nodeEdKeyPressCommand \"{}\" \"{}\"".format(node_editor, key_pressed))

    def toolbar_add_button(self, toolbar, tooltip, icon_name, command):
        a = QAction(icon=QIcon(os.path.join(self.icons_path, icon_name)), text="", parent=toolbar)
        a.setToolTip(tooltip) # hovering tooltip
        a.setStatusTip("Node Editor Plus: {}".format(tooltip)) # Maya's help line description
        a.triggered.connect(command)
        toolbar.addAction( a )

    def create_sidebar(self):
        # Reparents old NodeEditor into a new horizontal layout so we can add a sidebar to the window
        ctrl = OpenMayaUI.MQtUtil.findControl(self.node_editor)
        nodeEdPane = wrapInstance(int(ctrl), QWidget)
        nodeEdPaneParent = nodeEdPane.parent().parent().objectName()
        parent_ctrl = OpenMayaUI.MQtUtil.findControl(nodeEdPaneParent)
        original_widget = wrapInstance(int(parent_ctrl), QWidget)
        original_layout = original_widget.layout()

        # create our new layout and add it
        self.horizontal_main_layout = QHBoxLayout()
        original_layout.insertLayout( 0, self.horizontal_main_layout )

        # create the left side toolbar 
        self.left_toolbar = QToolBar()
        self.left_toolbar.setOrientation(Qt.Vertical)

        # comments buttons
        self.left_toolbar.addSeparator()
        self.toolbar_add_button(self.left_toolbar, "Create New Comment",   "comment_add.svg",    self.create_comment)
        self.toolbar_add_button(self.left_toolbar, "Delete Comment",       "comment_remove.svg", self.delete_comment)
        self.toolbar_add_button(self.left_toolbar, "Change Comment Color", "comment_color.svg",  self.color_comment)

        # align buttons
        self.left_toolbar.addSeparator()
        self.toolbar_add_button(self.left_toolbar, "Align Top",    "align_top.svg",    "")
        self.toolbar_add_button(self.left_toolbar, "Align Middle", "align_middle.svg", "")
        self.toolbar_add_button(self.left_toolbar, "Align Bottom", "align_bottom.svg", "")
        self.toolbar_add_button(self.left_toolbar, "Align Left",   "align_left.svg",   "")
        self.toolbar_add_button(self.left_toolbar, "Align Center", "align_center.svg", "")
        self.toolbar_add_button(self.left_toolbar, "Align Right",  "align_right.svg",  "")
        self.left_toolbar.addSeparator()

        # add the populated toolbar to the new layout we created
        self.horizontal_main_layout.addWidget(self.left_toolbar)

        # re-add the Node Editor to our new layout
        ctrl = OpenMayaUI.MQtUtil.findControl(self.node_editor)
        nodeEdPane = wrapInstance(int(ctrl), QWidget)
        self.horizontal_main_layout.addWidget(nodeEdPane)


    def align_nodes(self, alignIn):
        nodeAl = AlignNodes()
        if alignIn == "vertical":
            #print(nodeAl, alignIn)
            nodeAl.verticalAlign(self.get_selected_comments())
            cmds.nodeEditor( self.node_editor, edit=True, frameAll=True)
        if alignIn == "horizontal":
            #print(nodeAl, alignIn)
            nodeAl.horizontalAlign(self.get_selected_comments())
            cmds.nodeEditor( self.node_editor, edit=True, frameAll=True)


    def get_selected_comments(self):
        selected_items = []
        scene = getCurrentScene(self.node_editor)
        if scene:
            sel = scene.selectedItems()
            if sel:
                selected_items = sel
        return selected_items

    def color_comment(self):
        for item in self.get_selected_comments():
            if type(item) == custom_nodes.NEPComment:
                item.set_bg_color()

    def rename_comment(self):
        selected_items = self.get_selected_comments()
        if selected_items:
            # only rename 1 at a time
            if len(selected_items) == 1:
                if type(selected_items[0]) == custom_nodes.NEPComment:
                    selected_items[0].show_rename_edit_line()

    def delete_comment(self):
        for item in self.get_selected_comments():
            if type(item) == custom_nodes.NEPComment:
                item.delete()

        # at the end if nothing is left in scene, show the default HUD message
        scene = getCurrentScene(self.node_editor)
        if not scene.items():
            cmds.nodeEditor(self.node_editor, edit=True, hudMessage=(DEFAULT_HUD_MESSAGE, 3, 0))

    def create_comment(self):
        scene = getCurrentScene(self.node_editor)
        selected_items = self.get_selected_comments()
        if selected_items:
            items_list = []
            for item in selected_items:
                if type(item) == QGraphicsItem:
                    items_list.append(item)
            if items_list:
                final_rect = None
                for item in items_list:
                    if not final_rect:
                        final_rect = item.sceneBoundingRect()
                    else:
                        final_rect = final_rect.united(item.sceneBoundingRect())
                if final_rect:
                    com   = custom_nodes.NEPComment("", final_rect)
                    scene.addItem(com)
                    com.setPos( final_rect.x(), final_rect.y() )
        else:
            # if nothing selected and no items in scene, remove the default HUD message
            if not scene.items():
                cmds.nodeEditor(self.node_editor, edit=True, hudMessage=("", 3, 0))
            default_rect = QRectF(0, 0, 150, 50)
            com   = custom_nodes.NEPComment("", default_rect)
            scene.addItem(com)
            view = getCurrentView(self.node_editor)
            center = view.mapToScene(view.viewport().rect().center())
            com.setPos( center.x()-75, center.y()-25 )