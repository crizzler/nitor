// One swatch per colour the selected effect accepts, when it accepts more than one.
//
// A Flow rather than a layout: flows respect the explicit swatch size, which keeps these read as
// swatches instead of collapsing to hairlines.

// Delegates read the component's own ids, which requires explicit bound component behaviour.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls

Flow {
    id: slots

    required property var items
    required property color textColor

    signal slotChosen(int index)

    spacing: 6
    visible: items.length > 1

    Repeater {
        model: slots.items

        delegate: ItemDelegate {
            id: slot
            required property var modelData

            width: 36
            height: 28
            padding: 0
            hoverEnabled: true
            ToolTip.visible: hovered
            ToolTip.text: "Colour " + (slot.modelData.index + 1)
            background: Rectangle {
                radius: 5
                color: slot.modelData.hex
                border.width: slot.modelData.active ? 2 : 1
                border.color: slot.modelData.active
                              ? slots.textColor
                              : Qt.rgba(slots.textColor.r, slots.textColor.g, slots.textColor.b, 0.35)
            }
            onClicked: slots.slotChosen(slot.modelData.index)
        }
    }
}
