// Hex input. Accepts #RRGGBB, RRGGBB or the three-digit shorthand, and commits on Enter or on
// losing focus; an invalid value is rejected by the interface and explained in the status line.

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

RowLayout {
    id: field

    required property string colorHex

    signal committed(string text)

    spacing: 8

    TextField {
        id: input
        Layout.preferredWidth: 130
        enabled: field.enabled
        placeholderText: "#00AAFF"
        inputMethodHints: Qt.ImhNoPredictiveText | Qt.ImhPreferUppercase
        selectByMouse: true
        validator: RegularExpressionValidator {
            regularExpression: /^#?[0-9A-Fa-f]{3}([0-9A-Fa-f]{3})?$/
        }

        // Keep in step with the picker, but never fight the user while they are typing.
        Connections {
            target: field
            function onColorHexChanged() {
                if (!input.activeFocus) {
                    input.text = field.colorHex;
                }
            }
        }

        Component.onCompleted: text = field.colorHex

        onAccepted: field.committed(text)
        onEditingFinished: field.committed(text)

        ToolTip.visible: hovered && text.length > 0
        ToolTip.text: "Six hexadecimal digits, for example #00AAFF"
    }

    Label {
        text: "hex"
        opacity: 0.6
        Layout.alignment: Qt.AlignVCenter
    }
}
