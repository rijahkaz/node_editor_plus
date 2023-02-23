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
    temp_item_list = []
    def __init__(self, label, content_rect, NEP, bg_color=None, is_pinned=False):
        super().__init__()
        self._NEP = NEP
        self.pin_icon_off = QIcon(":/pinItem.png")
        self.pin_icon_on  = QIcon(":/pinON.png")

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)

        self.content_rect = QRectF(-10, -10, content_rect.width()+20, content_rect.height()+20)
        self.manhattanLength = self.content_rect.bottomRight().manhattanLength()
        if not label:
            label = "This is a new comment"
        self.set_label(label)

        self.create_pin_icon(is_pinned)

        if not bg_color:
            self.bg_color = COLOR_DEFAULT
        else:
            self.bg_color = QColor(bg_color)
            self.bg_color.setAlpha(50)
            self.update_label_color(self.bg_color)

        



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
        path.addRoundedRect(self.content_rect, 10, 10)
        
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
    def startAlign(self, caller, selectedItems, event):
        pass

    def stopAlign(self, caller, selectedItems, event):
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
               allVals.append(node.boundingRect().width())
               allVals.append(node.boundingRect().height())
               values.append(allVals)
               allVals = []
           return values

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
        middle = Top + Bottom / 2

        return middle

    def getCenter(self, Left, Right):
        center = Left + Right / 2

        return center

    def getMostRight(self, positionList): #+X
        rightMostX = max(position[0] for position in positionList)
        return rightMostX

    def leftAlign(self, graphicsList):
        xValue = self.getMostLeft(self.get_all_positions(graphicsList))
        #print(xValue)
        for node in graphicsList:
            node.setPos(xValue, node.pos().y())

    def centerAlign(self, graphicsList):
        xValue = self.getCenter(self.getMostLeft(self.get_all_positions(graphicsList)), self.getMostRight(self.get_all_positions(graphicsList)))
        #print(xValue)
        for node in graphicsList:
            node.setPos(xValue, node.pos().y())

    def rightAlign(self, graphicsList):
        xValue = self.getMostRight(self.get_all_positions(graphicsList))
        widthValue = self.getMostRight(self.get_all_values(graphicsList))
        for node in graphicsList:
            nodeWidth = node.boundingRect().width()
            widthDifference = widthValue - nodeWidth
            print("Inform:","xValue", xValue,"Width Value", widthValue, "Width Diffenrence", widthDifference, "node width", nodeWidth)
            if widthDifference != 0:
                xTemp = xValue + widthDifference
                node.setPos(xTemp, node.pos().y())
                print("xTemp", xTemp)
          

    def topAlign(self, graphicsList):
        yValue = self.getTop(self.get_all_positions(graphicsList))
        #print(yValue)
        for node in graphicsList:
            node.setPos(node.pos().x(), yValue)

    def middleAlign(self, graphicsList):
        yValue = self.getMiddle(self.getMostTop(self.get_all_positions(graphicsList)), self.getMostBottom(self.get_all_positions(graphicsList)))
        #print(yValue)
        for node in graphicsList:
            node.setPos(node.pos().x(), yValue)

    def bottomAlign(self, graphicsList):
        yValue = self.getBottom(self.get_all_positions(graphicsList))
        heightValue = self.getBottom(self.get_all_values(graphicsList))
        #print(yValue)
        for node in graphicsList:
            nodeHieight = node.boundingRect().height()
            heightDifference = heightValue - nodeHieight
            print("Inform:","xValue", yValue,"height Value", heightValue, "height Diffenrence", heightDifference, "node height",nodeHieight)
            if heightDifference != 0:
                yTemp = yValue + heightDifference
                node.setPos(node.pos().x(), yTemp)
                print("yTemp", yTemp)

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

