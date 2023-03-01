import base64
from functools import partial
from PySide2.QtWidgets import *
from PySide2.QtGui import *
from PySide2.QtCore import *

# color constants
COLOR_DEFAULT  = QColor(255,255,255,50)
COLOR_SELECTED = QColor(67, 252, 162, 255)
GRID_SIZE = 30 # eyeballed for snapping

class NEPRenameLabelFilter(QObject):
    # checks inputs during rename of a comment label
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

class NEPLabelFilter(QObject):
    # checks for double clicks on the comment label to trigger a rename
    def __init__(self, item):
        super().__init__()
        self.item = item

    def eventFilter(self, widget, event):
        if event.type() == QEvent.MouseButtonDblClick:
            self.item.show_rename_edit_line()
        return False

class NEPComment(QGraphicsItem):
    # Our new brand Comment class
    _NEP = None # reference to our Node Editor Plus class
    round_corners_size = 10
    label_rect = None
    label  = ""
    bg_color = None
    Qlabel = None
    content_rect    = None
    label_text_edit = None
    manhattanLength = 0
    is_showing_resize_cursor = False
    is_pinned = False
    pin_icon_off = None
    pin_icon_on  = None
    temp_item_list = []
    def __init__(self, label, content_rect, NEP, bg_color=None, is_pinned=False):
        super().__init__()
        self.node_type = type(self)
        self._NEP = NEP
        self.pin_icon_off = QIcon(":/pinItem.png")
        self.pin_icon_on  = QIcon(":/pinON.png")

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)

        self.content_rect = QRectF(-10, -10, content_rect.width()+20, content_rect.height()+20)
        self.update_manhattan_length()
        if not label and self.node_type == NEPComment:
            label = "This is a new comment"
        self.set_label(label)

        self.create_pin_icon(is_pinned)

        if not bg_color:
            self.bg_color = COLOR_DEFAULT
        else:
            self.bg_color = QColor(bg_color)
            if self.node_type == NEPComment:
                self.bg_color.setAlpha(50)
                self.update_label_color(self.bg_color)

    def update_manhattan_length(self):
        self.manhattanLength = self.content_rect.bottomRight().manhattanLength()

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

    def create_pin_icon(self, is_pinned):
        self.pin_button = QToolButton()
        self.pin_button.setFixedSize(24,24)
        if not is_pinned:
            self.pin_button.setIcon(self.pin_icon_off)
        else:
            self.pin_button.setIcon(self.pin_icon_on)
        self.pin_button.setIconSize(QSize(256,256))
        self.pin_button.setAttribute(Qt.WA_NoSystemBackground)
        self.pin_button.released.connect(self.toggle_pin)
        self.is_pinned = is_pinned

        pxy = QGraphicsProxyWidget(self)
        pxy.setWidget( self.pin_button )
        pxy.setPos( self.label_rect.x()-24, self.label_rect.y() )



    def set_label(self, label):
        self.label = label
        self.label_rect = QFontMetricsF(QFont()).boundingRect(label)
        self.label_rect.adjust(15, -20, 0, 0)

        if not self.Qlabel:
            self.Qlabel = QLabel(self.label)
            self._labelFilter = NEPLabelFilter(self)
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
            pen      = QPen(COLOR_SELECTED, 2)
        else:
            pen      = QPen(Qt.black, 2)

        path = QPainterPath()
        path.addRoundedRect(self.content_rect, self.round_corners_size, self.round_corners_size)

        painter.setPen(pen)
        painter.fillPath(path, self.bg_color )
        painter.drawPath(path)

    def show_rename_edit_line(self):
        if not self.label_text_edit:
            self.label_text_edit = QLineEdit(self.label)
            self.label_text_edit.editingFinished.connect(self.update_label)
            self._NEPRenameLabelFilter = NEPRenameLabelFilter(self)
            self.label_text_edit.installEventFilter(self._NEPRenameLabelFilter)
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

    def mousePressEvent(self, event, passive=False):
        ''' Start dragging - check overlapping nodes and parent to itself.
        Ignores if node is pinned.
        '''
        if not passive:
            self._NEP._drag_manager.start_drag(caller=self, scene=self.scene(), event=event)

        if self.is_pinned: return
        super().mousePressEvent(event)

        # closes edit if a click is detected (trying to drag)
        if self.label_text_edit:
            if self.label_text_edit.isVisible():
                self.cancel_update_label()

        if self.is_pinned: return

        children = self.childItems() # cache
        colliding_items = self.collidingItems()
        if colliding_items:
            for item in colliding_items:
                item_type = type(item)
                if item_type == QGraphicsItem or item_type == NEPImage:
                    if item not in children:
                        if item_type == NEPImage:
                            if not item.is_pinned:
                                self.add_child(item)
                        else: # this is a native Maya node
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
            self._NEP._drag_manager.mid_drag()

            # if it's not resizing then it's moving
            if self.is_pinned: return

            super().mouseMoveEvent(event)
            self.drag_update_hack()

    def mouseReleaseEvent(self, event, passive=None):
        ''' Dragging code - hack to update connections when dragging
        Ignores if node is pinned.
        '''
        if not passive:
            self._NEP._drag_manager.stop_drag(event=event)

        super().mouseReleaseEvent(event)

        # if released while resizing, update manhattanlength
        if self.is_showing_resize_cursor:
            self.update_manhattan_length()
            self.hide_resize_cursor() # force disable resize cursor

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
                    item_type = type(item)
                    if item_type == QGraphicsItem or item_type == NEPImage:
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
        if event.pos().manhattanLength() > self.manhattanLength - 24:
            if not self.is_showing_resize_cursor:
                self.show_resize_cursor()
        else:
            if self.is_showing_resize_cursor:
                self.hide_resize_cursor()

    def hoverLeaveEvent(self, event):
        if self.is_showing_resize_cursor:
            self.hide_resize_cursor()


    def set_bg_color(self, new_color=None):
        if not new_color:
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
                self.update_label_color(COLOR_SELECTED)
            else:
                self.update_label_color(self.bg_color)
        elif change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            if self._NEP.grid_snap:
                # eyeballed values that looked right-ish
                x = (round(value.x()/GRID_SIZE)*GRID_SIZE)-14
                y = (round(value.y()/GRID_SIZE)*GRID_SIZE)-14
                return( QPointF(x,y) )

        return QGraphicsItem.itemChange(self, change, value)


class NEPDragManager():
    # helper to propagate events to all comments nodes being dragged
    items_being_dragged = []
    def start_drag(self, caller, scene, event):
        # propagates mousePress events to all comments that are not the current one
        self.items_being_dragged = []
        selected_items = scene.selectedItems()
        if selected_items:
            for item in selected_items:
                # conditions
                if type(item) == NEPComment: # type NEPComment
                    if not item == caller: # not the caller
                        self.items_being_dragged.append(item)

        if self.items_being_dragged:
            for item in self.items_being_dragged:
                item.mousePressEvent(event, passive=True)

    def mid_drag(self):
        # propagate hack to update connections positions
        if self.items_being_dragged:
            for item in self.items_being_dragged:
                item.drag_update_hack()

    def stop_drag(self, event):
        # propagates mouseRelease to all comments that were being dragged and clears list
        if self.items_being_dragged:
            for item in self.items_being_dragged:
                item.mouseReleaseEvent(event, passive=True)
        self.items_being_dragged = []

class NEPNodeAligner():
    def startAlign(self, comment):
        #print("START")
        children = comment.childItems() # cache
        colliding_items = comment.collidingItems()
        if colliding_items:
            for item in colliding_items:
                item_type = type(item)
                if item_type == QGraphicsItem or item_type == NEPImage:
                    if item not in children:
                        if item_type == NEPImage:
                            if not item.is_pinned:
                                comment.add_child(item)
                        else: # this is a native Maya node
                            if not bool(item.flags() & QGraphicsItem.ItemIsFocusable): # skip searchbox
                                comment.add_child(item)

    def stopAlign(self, comment):
        #print("STOP")
        children = comment.childItems()
        if children:
            # hack to refresh C++ objects everytime children count change
            # so we're not pointing to objects that got deleted
            while True:
                children = comment.childItems()
                can_exit = True
                for item in children:
                    item_type = type(item)
                    if item_type == QGraphicsItem or item_type == NEPImage:
                        comment.remove_child(item)
                        can_exit = False
                        break
                if can_exit:
                    break
    def getFullLength(self, axis, graphicsList):
        fullLength = 0
        positionSize = 0
        for node in graphicsList:
            if axis == "x":
                positionSize = node.pos().x() + node.boundingRect().width()
                fullLength += positionSize
            elif axis == "y":
                positionSize = node.pos().y() + node.boundingRect().height()
                fullLength += positionSize
    
        return fullLength

    def getInitialNodeValue(self, axis, graphicsList):
        initialValue = 0
        firstNode = graphicsList[0]
        if axis == "x":
            initialValue = firstNode.pos().x()
        elif axis == "y":
            initialValue = firstNode.pos().y()
    
        return initialValue

    def get_all_positions(self, graphicsList):
        allVals = []
        values = []
        for node in graphicsList:
            allVals.append(node.pos().x())
            allVals.append(node.pos().y())
            values.append(allVals)
            allVals = []
        return values

    def get_all_values(self, graphicsList):
           allVals = []
           values = []
           for node in graphicsList:
               allVals.append(node.pos().x() + node.boundingRect().width())
               allVals.append(node.pos().y() + node.boundingRect().height())
               values.append(allVals)
               allVals = []
           return values

    def filterNodes(self, graphicsList):
        allowedNodes = []
        for node in graphicsList:
            if type(node) != QGraphicsPathItem:
                allowedNodes.append(node)
        return allowedNodes


    def sort_by_position(self, axis, graphicsList):
        valueNodes = []
        sortedNodes = []
        nodes = []
        index = 0

        if axis == "x":
            valueNodes = [(node, node.pos().x()) for node in self.filterNodes(graphicsList)]  
        elif axis == "y":
            valueNodes = [(node, node.pos().y()) for node in self.filterNodes(graphicsList)]

        sortedNodes = sorted(valueNodes, key=lambda x: x[1])

        for nodeTuple in sortedNodes:
            nodes.append(nodeTuple[0])
        #print("Nodes:", nodes)

        return nodes


    def get_space_between(self, axis, graphicsList):
        fLenght = 0
        spaceBetween = 0
        widths = 0
        heights = 0
        if axis == "x":
            mLeft = self.getMostLeft(self.get_all_positions(graphicsList))
            mRight = self.getMostRight(self.get_all_values(graphicsList))
            fLenght = mRight - mLeft
            for node in graphicsList:
                widths += node.boundingRect().width()
            spaceBetween = (fLenght - widths) / (len(graphicsList) - 1)
        elif axis == "y":
            mTop = self.getTop(self.get_all_positions(graphicsList))
            mBottom = self.getBottom(self.get_all_values(graphicsList))
            fLenght = mBottom - mTop
            for node in graphicsList:
                heights += node.boundingRect().height()
            spaceBetween = (fLenght - heights) / (len(graphicsList) - 1)

        return spaceBetween
        

    def getTop(self, positionList):  #+Y
        topMostY = min(position[1] for position in positionList)
        return topMostY


    def getBottom(self, positionList): #-Y
        bottomMostY = max(position[1] for position in positionList)
        return bottomMostY

    def getMostTop(self, positionList):  #+Y
        topMostY = max(position[1] for position in positionList)
        return topMostY


    def getMostBottom(self, positionList): #-Y
        bottomMostY = min(position[1] for position in positionList)
        return bottomMostY

    def getMostLeft(self, positionList): #-X
        leftMostX = min(position[0] for position in positionList)
        return leftMostX

    def getMiddle(self, Top, Bottom):
        middle = (Top + Bottom) / 2

        return middle

    def getCenter(self, Left, Right):
        center = (Left + Right) / 2

        return center

    def getMostRight(self, positionList): #+X
        rightMostX = max(position[0] for position in positionList)
        return rightMostX

    def leftAlign(self, graphicsList):
        values = self.sort_by_position("x", graphicsList)
        xValue = self.getMostLeft(self.get_all_positions(values))
        #print(xValue)
        for node in values:
            if type(node) == NEPComment:
                #print(node, " is comment")
                self.startAlign(node)
            node.setPos(xValue, node.pos().y())
            if type(node) == NEPComment:
                #print(node, " is comment")
                self.stopAlign(node)

    def centerAlign(self, graphicsList):
        values = self.sort_by_position("x", graphicsList)
        xValue = self.getCenter(self.getMostLeft(self.get_all_positions(values)), self.getMostRight(self.get_all_values(values)))
        #print(xValue)
        for node in values:
            if type(node) == NEPComment:
                #print(node, " is comment")
                self.startAlign(node)
            nodeCenter = node.boundingRect().width()/2
            node.setPos(xValue - nodeCenter, node.pos().y())
            if type(node) == NEPComment:
                #print(node, " is comment")
                self.stopAlign(node)

    def rightAlign(self, graphicsList):
        values = self.sort_by_position("x", graphicsList)
        widthValue = self.getMostRight(self.get_all_values(values))
        for node in values:
            if type(node) == NEPComment:
                #print(node, " is comment")
                self.startAlign(node)
            nodeWidth = node.boundingRect().width()
            xValue = widthValue - nodeWidth
            node.setPos(xValue, node.pos().y())
            if type(node) == NEPComment:
                #print(node, " is comment")
                self.stopAlign(node)
          

    def topAlign(self, graphicsList):
        values = self.sort_by_position("y", graphicsList)
        yValue = self.getTop(self.get_all_positions(values))
        #print(yValue)
        for node in values:
            if type(node) == NEPComment:
                #print(node, " is comment")
                self.startAlign(node)
            node.setPos(node.pos().x(), yValue)
            if type(node) == NEPComment:
                #print(node, " is comment")
                self.stopAlign(node)

    def middleAlign(self, graphicsList):
        values = self.sort_by_position("y", graphicsList)
        yValue = self.getMiddle(self.getMostTop(self.get_all_positions(values)), self.getMostBottom(self.get_all_values(values)))
        #print(yValue)
        for node in values:
            if type(node) == NEPComment:
                #print(node, " is comment")
                self.startAlign(node)
            nodeMiddle = node.boundingRect().height()/2
            node.setPos(node.pos().x(), yValue - nodeMiddle)
            if type(node) == NEPComment:
                #print(node, " is comment")
                self.stopAlign(node)

    def bottomAlign(self, graphicsList):
        values = self.sort_by_position("y", graphicsList)
        heightValue = self.getBottom(self.get_all_values(values))
        #print(yValue)
        for node in values:
            if type(node) == NEPComment:
                #print(node, " is comment")
                self.startAlign(node)
            nodeHieight = node.boundingRect().height()
            yValue = heightValue - nodeHieight
            node.setPos(node.pos().x(), yValue)
            if type(node) == NEPComment:
                #print(node, " is comment")
                self.stopAlign(node)

    def horizontalDistribute(self, graphicsList):
        values = self.sort_by_position("x", graphicsList)
        xValue = 0
        index= 0
        #Get gap between Nodes.
        spaceBetween = self.get_space_between("x", values)
        #Ititate through list and asign values.
        for node in values:
            #print(node)
            if type(node) == NEPComment:
                #print(node, " is comment")
                self.startAlign(node)

            if node != values[0]:
                xValue = values[index].pos().x() + values[index].boundingRect().width() + spaceBetween
                index+= 1
            else:
                xValue = node.pos().x()

            node.setPos(xValue, node.pos().y())
            if type(node) == NEPComment:
                #print(node, " is comment")
                self.stopAlign(node)

    def verticalDistribute(self, graphicsList):
        values = self.sort_by_position("y", graphicsList)
        yValue = 0
        index= 0
        #Get gap between Nodes.
        spaceBetween = self.get_space_between("y", values)
        #Ititate through list and asign values.
        for node in values:
            if type(node) == NEPComment:
                #print(node, " is comment")
                self.startAlign(node)
            if node != values[0]:
                yValue = values[index].pos().y() + values[index].boundingRect().height() + spaceBetween
                index+= 1
            else:
                yValue = node.pos().y()
            node.setPos(node.pos().x(), yValue)
            if type(node) == NEPComment:
                #print(node, " is comment")
                self.stopAlign(node)




class NEPImage(NEPComment):
    ''' Dragabble Image
    differences: has no label, cannot drag other nodes, can be dragged by comments
    '''
    pixmap = None
    img_index = -1 # saves img index to rebuild graph
    def __init__(self, label, content_rect, NEP, encoded_image, bg_color=None, is_pinned=False):
        self.round_corners_size = 1
        self.pixmap = QPixmap()
        self.pixmap.loadFromData(base64.b64decode(encoded_image), "PNG")

        if not content_rect: # if it's being created for the first time, use the image default size
            content_rect = self.pixmap.rect()
        super().__init__(label=" ", content_rect=content_rect, NEP=NEP, bg_color=None, is_pinned=False)

    def set_img_index(self, index):
        self.img_index = index

    # override mouse events to keep dragging working but skip all Comment-style calculations
    def mousePressEvent(self, event, passive=False):
        if self.is_pinned: return
        QGraphicsItem.mousePressEvent(self, event)

    def mouseMoveEvent(self, event):
        # calculate resize first
        if self.is_showing_resize_cursor:
            self.resize_comment( event )
        else:
            # if it's not resizing then it's moving
            if self.is_pinned: return
            QGraphicsItem.mouseMoveEvent(self, event)

    # override release event
    def mouseReleaseEvent(self, event, passive=None):
        # passive flag left there just in case to prevent errors
        QGraphicsItem.mouseReleaseEvent(self, event)

        # if released while resizing, update manhattanlength
        if self.is_showing_resize_cursor:
            self.update_manhattan_length()

        # don't move update anything if pinned, can't drag anyway
        if self.is_pinned: return

    # override paint
    def paint(self, painter, option, widget):
        if self.isSelected():
            pen      = QPen(COLOR_SELECTED, 2)
        else:
            pen      = QPen(QColor(0,0,0,0), 2)

        path = QPainterPath()
        path.addRoundedRect(self.content_rect, self.round_corners_size, self.round_corners_size)
        
        painter.setPen(pen)
        #painter.fillPath(path, self.bg_color )
        painter.drawPath(path)
        painter.drawPixmap(self.content_rect, self.pixmap, self.pixmap.rect())

class NEPSearchBox(QDialog):
    initial_width  = 450
    initial_height = 1
    comments_dict = {}
    buttons_list  = []
    NEP = None
    def __init__(self, NEP, comments_list, parent):
        super(NEPSearchBox, self).__init__(parent)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        size_policy = QSizePolicy()
        size_policy.setHorizontalPolicy(QSizePolicy.Expanding)
        self.setSizePolicy(size_policy)

        mouse_pos = QCursor.pos()
        self.NEP = NEP

        self.main_layout = QVBoxLayout()

        self.scroll = QScrollArea()
        self.widget = QWidget()
        self.layout = QVBoxLayout()

        self.filter_line_edit = QLineEdit()
        self.filter_line_edit.setFixedWidth(self.initial_width)
        self.filter_line_edit.setPlaceholderText("Type a substring of a comment to filter")
        self.filter_line_edit.textChanged.connect(self.apply_comment_filter)
        self.layout.addWidget(self.filter_line_edit)

        if not comments_list:
            # show simple layout
            self.filter_line_edit.setText("No comment nodes found in current Tab")
            self.filter_line_edit.setEnabled(False)
            self.setLayout(self.layout)
        else:
            # build the full scroll area
            for comment in comments_list:
                self.comments_dict[comment.label] = comment
                new_com_btn = QPushButton(comment.label)
                new_com_btn.setStyleSheet("color: {}".format(comment.bg_color.name()))
                new_com_btn.clicked.connect(partial(self.NEP.focus_item,comment))
                self.buttons_list.append(new_com_btn)
                self.layout.addWidget(new_com_btn)
            self.layout.addStretch() # only add stretch if comments

            self.widget.setLayout(self.layout)

            self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.scroll.setWidgetResizable(True)
            self.scroll.setFrameShape(QFrame.NoFrame)
            self.scroll.setWidget(self.widget)

            self.main_layout.addWidget(self.scroll)
            self.setLayout(self.main_layout)

            # stretches UI up to 5 buttons
            self.widget.resize(self.widget.sizeHint()+QSize(0,self.filter_line_edit.height()-20))
            self.initial_height = min(self.widget.height(), 350)

        self.setGeometry( mouse_pos.x()+20, mouse_pos.y(), self.initial_width, self.initial_height)


    def apply_comment_filter(self, filter_text):
        if filter_text:
            for btn in self.buttons_list:
                btn.setVisible(False)

            for btn in self.buttons_list:
                if filter_text.lower() in btn.text().lower():
                    btn.setVisible(True)
        else:
            for btn in self.buttons_list:
                btn.setVisible(True)

    def keyPressEvent( self, e ):
        # press ESC/TAB/ENTER closes UI
        if e.key() == Qt.Key_Escape or e.key() == Qt.Key_Tab or e.key() == Qt.Key_Enter:
            self.reject()

    def leaveEvent( self, e ):
        # leaving the UI with mouse pointer closes it
        self.reject()

    # static method to create the dialog
    @staticmethod
    def getResult(NEP, comments_list, parent):
        dialog = NEPSearchBox(NEP, comments_list, parent)
        if not comments_list:  # sets arbitrary height
            dialog_height = 20
        else:
            dialog_height = 350

        result = dialog.exec_()
        return False

def show_NEPSearchBox(NEP, comments_list, parent):
    return NEPSearchBox.getResult(NEP, comments_list, parent)
