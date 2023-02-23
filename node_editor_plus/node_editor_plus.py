import os, json
from functools import partial
from collections import OrderedDict
from maya import mel, cmds, OpenMayaUI
from shiboken2 import wrapInstance
from PySide2.QtWidgets import *
from PySide2.QtGui import *
from PySide2.QtCore import *
from node_editor_plus import custom_nodes

# version tracking
VERSION = "0.1.10"

# constants
WINDOW_NAME = "NodeEditorPlusWindow"
DEFAULT_HUD_MESSAGE = "Press Tab to create a node"
NODE_EDITOR_CFG = "MayaNodeEditorPlusSavedTabsInfo"

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

       

class NodeEditorPlus():
    node_editor = None
    icons_path = ""
    _drag_manager = None
    grid_snap = False
    def __init__(self):
        # manager to propagate drags between our custom nodes
        self._drag_manager = custom_nodes.NEPDragManager()
        self.aligner = custom_nodes.NEPNodeAligner()
        self.icons_path = os.path.join(os.path.dirname(__file__), "icons")

    def tab_change_callback(self):
        """ force new tabs to also recognize our hotkeys, this is weird since there is only 1 node editor
        but hotkeys only work in the first tab otherwise """
        cmds.nodeEditor(self.node_editor, edit=True, keyPressCommand=self.comment_key_callback)

        # intercept for our needs then call original callback
        parent   = cmds.setParent(query=True)
        showMenu = None # this doesn't seem it's being used at all in the function
        mel.eval("nodeEdUpdateUIByTab \"{}\" \"{}\"".format(self.node_editor, showMenu))

    def settings_changed_callback(self, *args):
        # intercept for our needs then call original callback
        #print(cmds.nodeEditor(self.node_editor, query=True, stateString=True))
        self.grid_snap = cmds.nodeEditor(self.node_editor, query=True, gridSnap=True)
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

        cmds.window(WINDOW_NAME, title="Node Editor Plus v{}".format(VERSION), widthHeight=(800, 550), closeCommand=self.window_close )
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

        # hack to not crash Maya, check for other ways
        QTimer.singleShot(500, self.load_nep_data_from_scene)
        #print(self.node_editor)

        

    def comment_key_callback(self, *args):
        ''' Detects keypresses'''
        node_editor = args[0]
        key_pressed = args[1]
        enter = True

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
        # align selected node(s) to the Top
        elif (mods & 1) > 0 and key_pressed == "W": 
            self.alignNodes("top")
            return True
        # align selected node(s) to the Middle
        elif (mods & 4) > 0 and key_pressed == "W": 
            self.alignNodes("middle")
            return True
        # align selected node(s) to the Bottom
        elif (mods & 1) > 0 and key_pressed == "S": 
            self.alignNodes("bottom")
            return True
        # align selected node(s) to the Left
        elif (mods & 1) > 0 and key_pressed == "A": 
            self.alignNodes("left")
            return True
        # align selected node(s) to the Center
        elif (mods & 4) > 0 and key_pressed == "A": 
            self.alignNodes("center")
            return True
        # align selected node(s) to the Right
        elif (mods & 1) > 0 and key_pressed == "D": 
            self.alignNodes("right")
            return True
        # distribute selected node(s) Horizontally
        elif (mods & 1) > 0 and key_pressed == "H": 
            self.alignNodes("horizontal")
            return True
        # distribute selected node(s) Vertically
        elif (mods & 1) > 0 and key_pressed == "V": 
           self.alignNodes("vertical")
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
        return mel.eval("nodeEdKeyPressCommand \"{}\" \"{}\"".format(node_editor, key_pressed))

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
        alignNode = False

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
        self.toolbar_add_button(self.left_toolbar, "Align Top",    "align_top.svg",    partial(self.alignNodes,"top"))
        self.toolbar_add_button(self.left_toolbar, "Align Middle", "align_middle.svg", partial(self.alignNodes,"middle"))
        self.toolbar_add_button(self.left_toolbar, "Align Bottom", "align_bottom.svg", partial(self.alignNodes,"bottom"))
        self.toolbar_add_button(self.left_toolbar, "Align Left",   "align_left.svg",   partial(self.alignNodes,"left"))
        self.toolbar_add_button(self.left_toolbar, "Align Center", "align_center.svg", partial(self.alignNodes,"center"))
        self.toolbar_add_button(self.left_toolbar, "Align Right",  "align_right.svg",  partial(self.alignNodes,"right"))
        self.toolbar_add_button(self.left_toolbar, "Distribute Horizontally", "distribute_horizontal.svg", partial(self.alignNodes,"horizontal"))
        self.toolbar_add_button(self.left_toolbar, "Distribute Vertically",   "distribute_vertical.svg",   partial(self.alignNodes,"vertical"))
        self.left_toolbar.addSeparator()

        # add the populated toolbar to the new layout we created
        self.horizontal_main_layout.addWidget(self.left_toolbar)

        # re-add the Node Editor to our new layout
        ctrl = OpenMayaUI.MQtUtil.findControl(self.node_editor)
        nodeEdPane = wrapInstance(int(ctrl), QWidget)
        alignNode = True
        self.horizontal_main_layout.addWidget(nodeEdPane)



    def alignNodes(self, alignIn):
        selected_items = self.get_selected_items()
        if not selected_items:
            print("No nodes selected")
            return

        if alignIn == "top":
            self.aligner.topAlign(selected_items)
        elif alignIn == "middle":
            self.aligner.middleAlign(selected_items)
        elif alignIn == "bottom":
            self.aligner.bottomAlign(selected_items)
        elif alignIn == "left":
            self.aligner.leftAlign(selected_items)
        elif alignIn == "center":
            self.aligner.centerAlign(selected_items)
        elif alignIn == "right":
            self.aligner.rightAlign(selected_items)
        elif alignIn == "horizontal":
            self.aligner.horizontalAlign(selected_items)
        elif alignIn == "vertical":
            self.aligner.verticalAlign(selected_items)

    def hide_default_HUD_message(self):
        cmds.nodeEditor(self.node_editor, edit=True, hudMessage=("", 3, 0))

    def get_selected_items(self):
        selected_items = []
        scene = getCurrentScene(self.node_editor)
        if scene:
            sel = scene.selectedItems()
            if sel:
                selected_items = sel
        return selected_items

    def color_comment(self):
        selected_items = self.get_selected_items()
        if selected_items:
            valid_comment_nodes = []
            for item in selected_items:
                if type(item) == custom_nodes.NEPComment:
                    valid_comment_nodes.append(item)

            if valid_comment_nodes:
                new_color = QColorDialog.getColor()
                for item in valid_comment_nodes:
                    item.set_bg_color(new_color)

    def rename_comment(self):
        selected_items = self.get_selected_items()
        if selected_items:
            # only rename 1 at a time
            if len(selected_items) == 1:
                if type(selected_items[0]) == custom_nodes.NEPComment:
                    selected_items[0].show_rename_edit_line()

    def delete_comment(self):
        for item in self.get_selected_items():
            if type(item) == custom_nodes.NEPComment:
                item.delete()

        # at the end if nothing is left in scene, show the default HUD message
        scene = getCurrentScene(self.node_editor)
        if not scene.items():
            cmds.nodeEditor(self.node_editor, edit=True, hudMessage=(DEFAULT_HUD_MESSAGE, 3, 0))

    def create_comment(self):
        scene = getCurrentScene(self.node_editor)
        selected_items = self.get_selected_items()
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
                    com   = custom_nodes.NEPComment("", final_rect, self)
                    scene.addItem(com)
                    com.setPos( final_rect.x(), final_rect.y() )
        else:
            # if nothing selected and no items in scene, remove the default HUD message
            if not scene.items():
                self.hide_default_HUD_message()
            default_rect = QRectF(0, 0, 150, 50)
            com   = custom_nodes.NEPComment("", default_rect, self)
            scene.addItem(com)
            view = getCurrentView(self.node_editor)
            center = view.mapToScene(view.viewport().rect().center())
            com.setPos( center.x()-75, center.y()-25 )

    def window_close(self):
        self.save_nep_data_to_scene()

    def save_nep_data_to_scene(self):
        tabs_dict = OrderedDict()
        tabs_names_list = []

        ctrl = OpenMayaUI.MQtUtil.findControl(self.node_editor)
        if ctrl is None:
            raise RuntimeError("Node editor is not open")
        nodeEdPane = wrapInstance(int(ctrl), QWidget)

        tabbar = nodeEdPane.findChild(QTabBar)
        for i in range(tabbar.count()-1): # removes +
            tabs_names_list.append(tabbar.tabText(i))

        stack = nodeEdPane.findChild(QStackedLayout)
        for i in range(stack.count()):
            children = stack.itemAt(i).widget().children()
            for child in children:
                if type(child) == QGraphicsView:
                    valid_items_list = []
                    for item in child.items():
                        if type(item) == custom_nodes.NEPComment:
                            valid_items_list.append(item)

                    tabs_dict[tabs_names_list[i]] = valid_items_list

        dump_dict = {}
        for tab in tabs_dict:
            dump_dict[tab] = []
            for item in tabs_dict[tab]:
                dump_dict[tab].append( {"label":item.label, "pos":{"x":item.pos().x(), "y":item.pos().y()}, "width":item.content_rect.width(), "height":item.content_rect.height(), "bg_color":item.bg_color.name(), "is_pinned":item.is_pinned} )

        if not cmds.objExists(NODE_EDITOR_CFG):
            cmds.createNode("network", name=NODE_EDITOR_CFG)

        if not cmds.attributeQuery("NEP_DATA", node=NODE_EDITOR_CFG, exists=True):
            cmds.addAttr(NODE_EDITOR_CFG, ln="NEP_DATA", dataType="string")

        cmds.setAttr(NODE_EDITOR_CFG+".NEP_DATA", json.dumps(dump_dict), type="string")

    def load_nep_data_from_scene(self):
        load_dict = {}

        if cmds.objExists(NODE_EDITOR_CFG):
            load_dict = json.loads(cmds.getAttr(NODE_EDITOR_CFG+'.NEP_DATA'))

        ctrl = OpenMayaUI.MQtUtil.findControl(self.node_editor)
        if ctrl is None:
            raise RuntimeError("Node editor is not open")
        nodeEdPane = wrapInstance(int(ctrl), QWidget)

        tabbar = nodeEdPane.findChild(QTabBar)
        stack  = nodeEdPane.findChild(QStackedLayout)
        for i in range(tabbar.count()-1): # removes +
            tab_name = tabbar.tabText(i)
            if tab_name in load_dict:
                stack.setCurrentIndex(i)
                graph_view = stack.currentWidget().findChild(QGraphicsView)
                scene = graph_view.scene()

                for comment in load_dict[tab_name]:
                    com   = custom_nodes.NEPComment(label=comment["label"], content_rect=QRectF(0, 0, comment["width"]-20, comment["height"]-20), NEP=self, bg_color=comment["bg_color"], is_pinned=comment["is_pinned"])
                    scene.addItem(com)
                    com.setPos(comment["pos"]["x"], comment["pos"]["y"])
