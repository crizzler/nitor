// Application-level brightness.
//
// Neither the HUE 2 protocol nor the Kraken drivers expose a brightness command for these LED
// channels, so this dims the colour Nitor sends. The interface says so rather than implying a
// hardware register exists.

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

RowLayout {
    id: control

    required property int brightness
    required property string effectiveColor

    signal moved(int percent)

    spacing: 12

    Slider {
        id: slider
        Layout.fillWidth: true
        from: 0
        to: 100
        stepSize: 1
        snapMode: Slider.SnapAlways
        enabled: control.enabled
        value: control.brightness

        onMoved: control.moved(Math.round(value))

        ToolTip.visible: hovered
        ToolTip.text: "Dims the colour Nitor sends (" + control.effectiveColor + ")"
    }

    Label {
        Layout.preferredWidth: 44
        horizontalAlignment: Text.AlignRight
        text: control.brightness + "%"
        opacity: control.enabled ? 1.0 : 0.5
    }
}
