#!/usr/bin/env python3
# -*- encoding:utf-8 -*-
"""
@Author : Lu Jin
@File   : app/movable_push_button.py
@Time   : 2023/05/11
@Desc   : 可移动按钮
"""

from PyQt5.QtWidgets import QApplication, QWidget, QPushButton
from PyQt5.QtCore import Qt


class MovablePushButton(QPushButton):
    """docstring for MovablePushButton
    可移动按钮组件
    """

    _mouse_press_pos = None
    _mouse_move_pos = None

    def mousePressEvent(self, event):  # pylint: disable=invalid-name
        if event.button() == Qt.LeftButton:
            self._mouse_press_pos = event.globalPos()
            self._mouse_move_pos = event.globalPos()

        super(MovablePushButton, self).mousePressEvent(event)

    def mouseMoveEvent(self, event):  # pylint: disable=invalid-name
        if event.buttons() == Qt.LeftButton:
            # adjust offset from clicked point to origin of widget
            curr_pos = self.mapToGlobal(self.pos())
            global_pos = event.globalPos()
            diff = global_pos - self._mouse_move_pos
            if diff.manhattanLength() < 20:
                event.ignore()
                return
            new_pos = self.mapFromGlobal(curr_pos + diff)
            if self.parent():
                right = self.parent().geometry().width()
                bottom = self.parent().geometry().height()

                if new_pos.x() < 0:
                    new_pos.setX(0)
                elif new_pos.x() > right - self.width():
                    new_pos.setX(right - self.width())

                if new_pos.y() < 0:
                    new_pos.setY(0)
                elif new_pos.y() > bottom - self.height():
                    new_pos.setY(bottom - self.height())

                self.move(new_pos)
            self._mouse_move_pos = global_pos

        super(MovablePushButton, self).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):  # pylint: disable=invalid-name
        if self._mouse_press_pos is not None:
            moved = event.globalPos() - self._mouse_press_pos
            if moved.manhattanLength() > 3:
                event.ignore()
                self.setDown(False)
                return

        super(MovablePushButton, self).mouseReleaseEvent(event)


def clicked():
    print("click as normal!")


if __name__ == "__main__":
    app = QApplication([])
    w = QWidget()
    w.resize(800, 600)

    button = MovablePushButton("Drag", w)
    button.clicked.connect(clicked)

    w.show()
    app.exec_()
