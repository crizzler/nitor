// The small, deliberately limited set of preset colours.

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Flow {
    id: presets

    required property var items
    required property string current
    required property color textColor
    required property color highlightColor

    signal picked(string name)

    spacing: 6

    Repeater {
        model: presets.items

        delegate: ItemDelegate {
            id: swatch
            required property var modelData

            width: 30
            height: 30
            enabled: presets.enabled
            padding: 0
            hoverEnabled: true
            ToolTip.visible: hovered
            ToolTip.text: swatch.modelData.name
            // The chosen preset is marked by its border rather than by a separate label, which keeps
            // the row compact.
            background: Rectangle {
                radius: 6
                color: swatch.modelData.hex
                border.width: swatch.hovered || swatch.modelData.hex === presets.current ? 2 : 1
                border.color: swatch.hovered || swatch.modelData.hex === presets.current
                              ? presets.highlightColor
                              : Qt.rgba(presets.textColor.r, presets.textColor.g, presets.textColor.b, 0.3)
            }
            onClicked: presets.picked(swatch.modelData.name)
        }
    }
}
