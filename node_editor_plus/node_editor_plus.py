import os, json, base64
from functools import partial
from collections import OrderedDict
from maya import mel, cmds, OpenMayaUI
from shiboken2 import wrapInstance
from PySide2.QtWidgets import *
from PySide2.QtGui import *
from PySide2.QtCore import *
from node_editor_plus import custom_nodes

# version tracking
VERSION = "0.1.12"

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

       
class NEPMousePosFilter(QObject):
    # tracks mouse position on certain actions like graphing in/out connections
    def __init__(self, NEP):
        super().__init__()
        self._NEP = NEP

    def eventFilter(self, widget, event):
        if event.type() == QEvent.Type.GraphicsSceneMouseMove:
            self._NEP.mouse_pos = event.scenePos()
        return False

class NodeEditorPlus():
    node_editor = None
    icons_path = ""
    _drag_manager = None
    _mouse_pos_filter = None
    mouse_pos = None
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

        # force additive to be ON to avoid crashing Maya
        cmds.nodeEditor(self.node_editor, edit=True, additiveGraphingMode=False)

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

        # tracks mouse position on certain actions like graphing in/out connections
        self._mouse_pos_filter = NEPMousePosFilter(self)
        scene = getCurrentScene(self.node_editor)
        scene.installEventFilter(self._mouse_pos_filter)

        # change a couple things of the original graph to keep ours more stable
        self.override_clear_function()
        self.override_remove_function()

    @staticmethod
    def is_graph_extended(ned=None):
        # checks if we have our custom nodes in the provided graph
        return_value = False
        scene = getCurrentScene(ned)
        if scene:
            scene_items = scene.items()
            if scene_items:
                for item in scene_items:
                    if type(item) in [custom_nodes.NEPComment, custom_nodes.NEPImage]:
                        return_value = True
                        break
        return return_value

    @staticmethod
    def clear_graph(ned=None):
        # clean clear procedure so we don't crash Maya
        scene = getCurrentScene(ned)
        if scene:
            scene_items = scene.items()
            if scene_items:
                for item in scene_items:
                    if type(item) in [custom_nodes.NEPComment, custom_nodes.NEPImage]:
                        item.delete()

    def override_clear_function(self):
        # to check if the current graph has our custom nodes
        new_cmd = '''global proc nodeEdClearAll(string $ned)
                    {
                        if ($ned != "")
                        {
                            python("from node_editor_plus import node_editor_plus");
                            python("import importlib; importlib.reload(node_editor_plus)");
                            if (`python("node_editor_plus.NodeEditorPlus.is_graph_extended(\\"'''+self.node_editor+'''\\")")`)
                            {
                                python("node_editor_plus.NodeEditorPlus.clear_graph(\\"'''+self.node_editor+'''\\")");
                            }
                            nodeEditor -e -rootNode "" $ned;
                        }
                    }'''
        mel.eval(new_cmd)

    def restore_clear_function(self):
        # avoid errors if our UI is closed
        old_cmd = '''global proc nodeEdClearAll(string $ned)
                    {
                        if ($ned != "") {
                            nodeEditor -e -rootNode "" $ned;
                        }
                    }'''
        mel.eval(old_cmd)

    def override_remove_function(self):
        new_cmd = '''global proc nodeEdRemoveSelected(string $ned)
                    {
                        if ($ned != "") {
                            python("from node_editor_plus import node_editor_plus");
                            python("import importlib; importlib.reload(node_editor_plus)");
                            if (`python("node_editor_plus.NodeEditorPlus.is_graph_extended(\\"'''+self.node_editor+'''\\")")`)
                            {
                                python("node_editor_plus.NodeEditorPlus.static_delete_item(\\"'''+self.node_editor+'''\\")");
                            }
                            nodeEditor -e -rem "" $ned;
                        }
                    }'''
        mel.eval(new_cmd)

    def restore_remove_function(self):
        old_cmd = '''global proc nodeEdRemoveSelected(string $ned)
                    {
                        if ($ned != "") {
                            nodeEditor -e -rem "" $ned;
                        }
                    }'''
        mel.eval(old_cmd)

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
        # graph input connection
        elif key_pressed == "I":
            self.graph_connection("input")
            return True
        elif key_pressed == "O":
            self.graph_connection("output")
            return True
        # delete selected comment(s)
        elif key_pressed == "Del" or key_pressed == "Backspace": 
            self.delete_item()
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
        if not icon_name.startswith(":"):
            a = QAction(icon=QIcon(os.path.join(self.icons_path, icon_name)), text="", parent=toolbar)
        else:
            a = QAction(icon=QIcon(icon_name), text="", parent=toolbar)
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
        self.toolbar_add_button(self.left_toolbar, "Delete Item",          "comment_remove.svg", self.delete_item)
        self.toolbar_add_button(self.left_toolbar, "Change Comment Color", "comment_color.svg",  self.color_comment)
        self.toolbar_add_button(self.left_toolbar, "Add Image to Graph",   "image_add.svg",      self.pick_new_image)
        
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

    def delete_item(self, items_list=None):
        if not items_list:
            items_list = self.get_selected_items()

        for item in items_list:
            if type(item) in [custom_nodes.NEPComment, custom_nodes.NEPImage]:
                item.delete()

        # at the end if nothing is left in scene, show the default HUD message
        scene = getCurrentScene(self.node_editor)
        if not scene.items():
            cmds.nodeEditor(self.node_editor, edit=True, hudMessage=(DEFAULT_HUD_MESSAGE, 3, 0))

    @staticmethod
    def static_delete_item(ned):
        scene = getCurrentScene(ned)
        if scene:
            selected_items = scene.selectedItems()
            if selected_items:
                for item in selected_items:
                    if type(item) in [custom_nodes.NEPComment, custom_nodes.NEPImage]:
                        item.delete()

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

    def pick_new_image(self):
        image_path = QFileDialog.getOpenFileName(parent=None, caption='Please select an image file', filter="*.png")
        if not image_path:
            return

        try:
            encoded_image = None
            with open(image_path[0], 'rb') as image_file:
                encoded_image = base64.b64encode(image_file.read())

            if encoded_image:
                attr_name = "IMG_LIST"
                create_dict = self.create_nep_data(create_string_array_attr=attr_name)
                if create_dict["created_attr"]:
                    old_array = []
                    size = 0
                else:
                    old_array = cmds.getAttr(NODE_EDITOR_CFG+"."+attr_name)
                    size = len(old_array)
                new_array = old_array + [encoded_image]
                
                cmds.setAttr(NODE_EDITOR_CFG+"."+attr_name, size+1, *new_array, type="stringArray")

                self.create_image(encoded_image=encoded_image, img_index=size)
        except:
            cmds.error("Could not load image: {}".format(image_path[0]))

    def create_image(self, encoded_image, img_index):
        scene = getCurrentScene(self.node_editor)
        # if nothing selected and no items in scene, remove the default HUD message
        if not scene.items():
            self.hide_default_HUD_message()

        img   = custom_nodes.NEPImage(label="", content_rect=None, NEP=self, encoded_image=encoded_image)
        img.set_img_index(img_index)
        scene.addItem(img)
        view = getCurrentView(self.node_editor)
        center = view.mapToScene(view.viewport().rect().center())
        img.setPos( center.x()-75, center.y()-25 )

    def graph_connection(self, conn_type="output"):
        plug_under_cursor = cmds.nodeEditor(self.node_editor, feedbackPlug=True, query=True)
        if plug_under_cursor:
            con_nodes = []
            if conn_type == "input":
                con_nodes = cmds.listConnections(plug_under_cursor, source=True, destination=False, skipConversionNodes=False)
            elif conn_type == "output":
                con_nodes = cmds.listConnections(plug_under_cursor, source=False, destination=True, skipConversionNodes=False)
            
            if con_nodes:
                source_node = cmds.nodeEditor(self.node_editor, feedbackNode=True, query=True)
                cmds.nodeEditor(self.node_editor, selectNode="", edit=True) # clear
                cmds.nodeEditor(self.node_editor, selectNode=source_node, edit=True)

                source_item = self.get_selected_items()[0]

                # first add them to make sure they exist in the graph
                for node in con_nodes:
                    cmds.nodeEditor(self.node_editor, addNode=node, layout=False, edit=True)

                # now grab their items
                cmds.select(con_nodes)
                cmds.refresh(force=True)
                QTimer.singleShot(100, partial(self.graph_connection_organize, source_item, conn_type))

    def graph_connection_organize(self, source_item, conn_type):
        # roughly aligns new added nodes to the source_item
        cmds.nodeEditor(self.node_editor, nodeViewMode="connected", edit=True)
        dest_items = self.get_selected_items()

        # "inputs" align to the left
        if conn_type == "input":
            y_offset = source_item.pos().y()
            for item in dest_items:
                item.setPos( source_item.pos().x()-(item.boundingRect().width())*1.5, y_offset+20 )
                y_offset = item.pos().y() + item.boundingRect().height()

        # "outputs" align to the right
        elif conn_type == "output":
            y_offset = source_item.pos().y()
            for item in dest_items:
                item.setPos( source_item.pos().x()+(item.boundingRect().width())*1.5, y_offset+20 )
                y_offset = +item.pos().y() + item.boundingRect().height()


    def window_close(self):
        # custom nodes persistence
        self.save_nep_data_to_scene()
        # avoid errors if user launches original Node Editor
        self.restore_clear_function()
        self.restore_remove_function()

    def create_nep_data(self, create_string_attr=None, create_string_array_attr=None):
        return_dict = {"created_node":False, "created_attr":False}
        if not cmds.objExists(NODE_EDITOR_CFG):
            cmds.createNode("network", name=NODE_EDITOR_CFG)
            cmds.lockNode(NODE_EDITOR_CFG, lock=True) # please don't delete me
            return_dict["created_node"] = True

        if create_string_attr:
            if not cmds.attributeQuery(create_string_attr, node=NODE_EDITOR_CFG, exists=True):
                cmds.lockNode(NODE_EDITOR_CFG, lock=False)
                cmds.addAttr(NODE_EDITOR_CFG, ln=create_string_attr, dataType="string")
                cmds.lockNode(NODE_EDITOR_CFG, lock=True)
                return_dict["created_attr"] = True
        elif create_string_array_attr:
            if not cmds.attributeQuery(create_string_array_attr, node=NODE_EDITOR_CFG, exists=True):
                cmds.lockNode(NODE_EDITOR_CFG, lock=False)
                cmds.addAttr(NODE_EDITOR_CFG, ln=create_string_array_attr, dataType="stringArray")
                cmds.lockNode(NODE_EDITOR_CFG, lock=True)
                return_dict["created_attr"] = True

        return return_dict

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
                        if type(item) in [custom_nodes.NEPComment, custom_nodes.NEPImage]:
                            valid_items_list.append(item)

                    tabs_dict[tabs_names_list[i]] = valid_items_list

        dump_dict = {}
        for tab in tabs_dict:
            dump_dict[tab] = []
            for item in tabs_dict[tab]:
                item_type = type(item)
                if   item_type == custom_nodes.NEPComment:
                    dump_dict[tab].append( {"nep_type":"comment", "label":item.label,         "pos":{"x":item.pos().x(), "y":item.pos().y()}, "width":item.content_rect.width(), "height":item.content_rect.height(), "bg_color":item.bg_color.name(), "is_pinned":item.is_pinned} )
                elif item_type == custom_nodes.NEPImage:
                    dump_dict[tab].append( {"nep_type":"image",   "img_index":item.img_index, "pos":{"x":item.pos().x(), "y":item.pos().y()}, "width":item.content_rect.width(), "height":item.content_rect.height(), "bg_color":item.bg_color.name(), "is_pinned":item.is_pinned} )
                

        self.create_nep_data(create_string_attr="NEP_DATA")
        cmds.setAttr(NODE_EDITOR_CFG+".NEP_DATA", json.dumps(dump_dict), type="string")

    def load_nep_data_from_scene(self):
        load_dict = {}

        if cmds.objExists(NODE_EDITOR_CFG):
            if cmds.attributeQuery("NEP_DATA", node=NODE_EDITOR_CFG, exists=True):
                load_dict = json.loads(cmds.getAttr(NODE_EDITOR_CFG+'.NEP_DATA'))
            else:
                return

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

                for item in load_dict[tab_name]:
                    if   item["nep_type"] == "comment":
                        nep_item = custom_nodes.NEPComment(label=item["label"], content_rect=QRectF(0, 0, item["width"]-20, item["height"]-20), NEP=self, bg_color=item["bg_color"], is_pinned=item["is_pinned"])
                    elif item["nep_type"] == "image":
                        encoded_image = cmds.getAttr(NODE_EDITOR_CFG+".IMG_LIST")[item["img_index"]]
                        nep_item = custom_nodes.NEPImage(label="", encoded_image=encoded_image, content_rect=QRectF(0, 0, item["width"]-20, item["height"]-20), NEP=self, bg_color=item["bg_color"], is_pinned=item["is_pinned"])
                        nep_item.set_img_index(item["img_index"])
                    scene.addItem(nep_item)

                    if item["nep_type"] == "comment":
                        nep_item.setZValue(-1)
                    nep_item.setPos(item["pos"]["x"], item["pos"]["y"])
