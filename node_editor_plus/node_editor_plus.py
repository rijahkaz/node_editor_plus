import os
from maya import mel, cmds, OpenMayaUI
from shiboken2 import wrapInstance
from PySide2.QtWidgets import *
from PySide2.QtGui import *
from PySide2.QtCore import *

VERSION = "0.1.4"

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

class RenameLabelFilter(QObject):
    def __init__(self, item):
        super().__init__()
        self.item = item

    def eventFilter(self, widget, event):
        if event.type() == QEvent.Type.KeyPress:
            if   event.key() == Qt.Key_Escape:
                self.item.cancel_update_label()
            elif event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
                self.item.label_text_edit.setVisible(False)

        return False

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
       

class LabelFilter(QObject):
    def __init__(self, item):
        super().__init__()
        self.item = item

    def eventFilter(self, widget, event):
        if event.type() == QEvent.MouseButtonDblClick:
            self.item.show_rename_edit_line()
        return False

class NEPComment(QGraphicsItem):
    label_rect = None
    label  = ""
    Qlabel = None
    content_rect    = None
    label_text_edit = None
    manhattanLength = 0
    is_showing_resize_cursor = False
    is_pinned = False
    pin_icon_off = None
    pin_icon_on  = None
    COLOR_DEFAULT  = QColor(255,255,255,50)
    COLOR_SELECTED = QColor(67, 252, 162, 255)
    temp_item_list = []
    def __init__(self, label, content_rect):
        super().__init__()
        self.pin_icon_off = QIcon(":/pinItem.png")
        self.pin_icon_on  = QIcon(":/pinON.png")

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.content_rect = QRectF(-10, -10, content_rect.width()+20, content_rect.height()+20)
        self.manhattanLength = self.content_rect.bottomRight().manhattanLength()
        self.set_label(label)

        self.create_pin_icon()

        self.bg_color = self.COLOR_DEFAULT
        self.setAcceptHoverEvents(True)



    def add_child(self, item):
        # On start drag, parents and fixes position of overlapping nodes
        old_pos = item.scenePos()
        item.setParentItem(self)
        item.setPos(self.sceneTransform().inverted()[0].map(old_pos))

    def remove_child(self, item):
        # On stop drag, unparents and fixes position of child nodes
        scene = self.scene()
        old_pos = item.scenePos()
        self.temp_item_list.append(item) # hack to avoid item to be deleted, seems to work
        item.setParentItem( None )
        #scene.addItem(item)
        item.setPos( old_pos )

    def delete(self):
        scene = self.scene()
        scene.removeItem(self)

    def toggle_pin(self):
        if self.is_pinned:
            self.is_pinned = False
            self.pin_button.setIcon(self.pin_icon_off)
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        else:
            self.is_pinned = True
            self.pin_button.setIcon(self.pin_icon_on)
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)

    def create_pin_icon(self):
        self.pin_button = QToolButton()
        self.pin_button.setFixedSize(24,24)
        self.pin_button.setIcon(self.pin_icon_off)
        self.pin_button.setIconSize(QSize(256,256))
        self.pin_button.setAttribute(Qt.WA_NoSystemBackground)
        self.pin_button.released.connect(self.toggle_pin)
        self.is_pinned = False

        pxy = QGraphicsProxyWidget(self)
        pxy.setWidget( self.pin_button )
        pxy.setPos( self.label_rect.x()-24, self.label_rect.y() )



    def set_label(self, label):
        self.label = label
        self.label_rect = QFontMetricsF(QFont()).boundingRect(label)
        self.label_rect.adjust(15, -20, 0, 0)

        if not self.Qlabel:
            self.Qlabel = QLabel(self.label)
            self._labelFilter = LabelFilter(self)
            self.Qlabel.installEventFilter(self._labelFilter)
            self.Qlabel.setAttribute(Qt.WA_NoSystemBackground)
            pxy = QGraphicsProxyWidget(self)
            pxy.setWidget( self.Qlabel )
            pxy.setPos( self.label_rect.x(), self.label_rect.y() )
        else:
            self.Qlabel.setText(self.label)
        
    def boundingRect(self):
        return self.content_rect

    def paint(self, painter, option, widget):
        if self.isSelected():
            pen      = QPen(self.COLOR_SELECTED, 2)
        else:
            pen      = QPen(Qt.black, 2)

        path = QPainterPath()
        path.addRoundedRect(self.content_rect, 10, 10)
        
        painter.setPen(pen)
        painter.fillPath(path, self.bg_color )
        painter.drawPath(path)

    def show_rename_edit_line(self):
        if not self.label_text_edit:
            self.label_text_edit = QLineEdit(self.label)
            self.label_text_edit.editingFinished.connect(self.update_label)
            self._renameLabelFilter = RenameLabelFilter(self)
            self.label_text_edit.installEventFilter(self._renameLabelFilter)
            pxy = QGraphicsProxyWidget(self)
            pxy.setWidget( self.label_text_edit )

            pxy.setPos( self.label_rect.x(), self.label_rect.y() )
        else:
            self.label_text_edit.setVisible(True)
        self.Qlabel.setVisible(False)

        self.label_text_edit.setFixedWidth( max(min(self.label_rect.width(), 500), 150) )
        self.label_text_edit.selectAll()
        self.label_text_edit.setFocus()
        self._old_label = self.label_text_edit.text()
        
    def cancel_update_label(self):
        self.label_text_edit.setText(self._old_label)
        self.label_text_edit.setVisible(False)
        self.Qlabel.setVisible(True)

    def update_label(self, *args):
        new_label = self.label_text_edit.text()
        if new_label:
            self.set_label( new_label )
            self.label_text_edit.setVisible(False)
            self.Qlabel.setVisible(True)

    def mousePressEvent(self, event):
        ''' Start dragging - check overlapping nodes and parent to itself.
        Ignores if node is pinned.
        '''
        if self.is_pinned: return
        # closes edit if a click is detected (trying to drag)
        super().mousePressEvent(event)
        if self.label_text_edit:
            if self.label_text_edit.isVisible():
                self.cancel_update_label()

        if self.is_pinned: return

        children = self.childItems() # cache
        colliding_items = self.collidingItems()
        if colliding_items:
            for item in colliding_items:
                if type(item) == QGraphicsItem:
                    if item not in children:
                        if not bool(item.flags() & QGraphicsItem.ItemIsFocusable): # skip searchbox
                            self.add_child(item)


    def drag_update_hack(self):
        children = self.childItems()
        if children:
            for ch in children:
                ch.moveBy(0.000001, 0)

    def mouseMoveEvent(self, event):
        ''' Dragging code - hack to update connections when dragging
        Ignores if node is pinned.
        '''
        # calculate resize first
        if self.is_showing_resize_cursor:
            self.resize_comment( event )
        else:
            # if it's not resizing then it's moving
            if self.is_pinned: return

            super().mouseMoveEvent(event)
            self.drag_update_hack()

    def mouseReleaseEvent(self, event):
        ''' Dragging code - hack to update connections when dragging
        Ignores if node is pinned.
        '''
        super().mouseReleaseEvent(event)

        # if released while dragging, update manhattanlength
        if self.is_showing_resize_cursor:
            self.manhattanLength = self.content_rect.bottomRight().manhattanLength()

        # don't move update anything if pinned, can't drag anyway
        if self.is_pinned: return
        
        self.drag_update_hack()

        children = self.childItems()
        if children:
            # hack to refresh C++ objects everytime children count change
            # so we're not pointing to objects that got deleted
            while True:
                children = self.childItems()
                can_exit = True
                for item in children:
                    if type(item) == QGraphicsItem:
                        self.remove_child(item)
                        can_exit = False
                        break
                if can_exit:
                    break

    def resize_comment(self, event):
        self.prepareGeometryChange()
        self.content_rect.setWidth(event.pos().x()+10) # hardcoded offset
        self.content_rect.setHeight(event.pos().y()+10)


    def show_resize_cursor(self):
        self.is_showing_resize_cursor = True
        QApplication.setOverrideCursor(QCursor(Qt.SizeFDiagCursor))

    def hide_resize_cursor(self):
        QApplication.restoreOverrideCursor()
        self.is_showing_resize_cursor = False

    def hoverMoveEvent(self, event):
        if event.pos().manhattanLength() > self.manhattanLength - 12:
            if not self.is_showing_resize_cursor:
                self.show_resize_cursor()
        else:
            if self.is_showing_resize_cursor:
                self.hide_resize_cursor()

    def hoverLeaveEvent(self, event):
        if self.is_showing_resize_cursor:
            self.hide_resize_cursor()


    def set_bg_color(self, *args):
        new_color = QColorDialog.getColor()
        if new_color.isValid():
            new_color.setAlpha(50)
            self.bg_color = new_color
            self.update_label_color(new_color)

    def update_label_color(self, QColor):
        self.Qlabel.setStyleSheet("QLabel { color : "+QColor.name()+"; }")

    def itemChange(self, change, value):
        # tracks select status
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedChange:
            if value:
                self.update_label_color(self.COLOR_SELECTED)
            else:
                self.update_label_color(self.bg_color)

        return QGraphicsItem.itemChange(self, change, value)


    

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

    def ui(self):
        win = cmds.window(title="Node Editor Plus v{}".format(VERSION), widthHeight=(800, 550) )
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

        cmds.showWindow(win)

        

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
            if type(item) == NEPComment:
                item.set_bg_color()

    def rename_comment(self):
        selected_items = self.get_selected_comments()
        if selected_items:
            # only rename 1 at a time
            if len(selected_items) == 1:
                if type(selected_items[0]) == NEPComment:
                    selected_items[0].show_rename_edit_line()

    def delete_comment(self):
        for item in self.get_selected_comments():
            if type(item) == NEPComment:
                item.delete()

    def create_comment(self):
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
                    com   = NEPComment("This is a new comment", final_rect)
                    scene = getCurrentScene(self.node_editor)
                    scene.addItem(com)
                    com.setPos( final_rect.x(), final_rect.y() )
        else:
            default_rect = QRectF(0, 0, 150, 50)
            com   = NEPComment("This is a new comment", default_rect)
            scene = getCurrentScene(self.node_editor)
            scene.addItem(com)
            view = getCurrentView(self.node_editor)
            center = view.mapToScene(view.viewport().rect().center())
            com.setPos( center.x()-75, center.y()-25 )