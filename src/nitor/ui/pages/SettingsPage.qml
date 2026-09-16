// Settings, kept deliberately small: startup behaviour, diagnostics and where the settings live.

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

Page {
    id: page

    required property var app

    ScrollView {
        id: scroller
        anchors.fill: parent
        clip: true
        contentWidth: availableWidth

        ColumnLayout {
            width: scroller.availableWidth
            spacing: 16

            SectionCard {
                Layout.fillWidth: true
                Layout.margins: 20
                title: "Startup"
                subtitle: "Lighting can be reapplied at login without leaving this window open"

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    Switch {
                        id: loginSwitch
                        text: "Apply my lighting settings when I log in"
                        enabled: page.app.autostartSupported
                        checked: page.app.applyOnLogin
                        onToggled: page.app.setApplyOnLogin(checked)
                    }

                    Item {
                        Layout.fillWidth: true
                    }
                }

                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    opacity: 0.7
                    visible: !page.app.autostartSupported
                    text: "This system does not use systemd, so Nitor cannot register a login service. " +
                          "Start it from your desktop's autostart settings instead, with the argument --apply-saved."
                }

                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    opacity: 0.7
                    visible: page.app.autostartDetail.length > 0
                    text: page.app.autostartDetail
                }

                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    opacity: 0.7
                    text: "A one-shot systemd --user unit applies the saved lighting and exits. " +
                          "Nothing stays running in the background, and no root access is needed."
                }
            }

            SectionCard {
                Layout.fillWidth: true
                Layout.leftMargin: 20
                Layout.rightMargin: 20
                title: "Diagnostics"
                subtitle: "A report to paste into an issue: versions, detected USB ids, channels and permissions. " +
                          "It contains no user names, host names or serial numbers."

                RowLayout {
                    spacing: 8

                    Button {
                        text: "Copy diagnostics"
                        onClicked: page.app.copyToClipboard(page.app.diagnosticsReport())
                    }

                    Label {
                        Layout.fillWidth: true
                        opacity: 0.6
                        font.pointSize: Math.round(page.app.baseFontPointSize * 0.9)
                        text: "Settings file: " + page.app.configPath
                        elide: Text.ElideMiddle
                    }
                }

                ScrollView {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 260
                    clip: true

                    TextArea {
                        readOnly: true
                        selectByMouse: true
                        wrapMode: TextEdit.NoWrap
                        font.family: "monospace"
                        font.pointSize: Math.round(page.app.baseFontPointSize * 0.9)
                        text: page.app.diagnosticsText
                    }
                }
            }

            SectionCard {
                Layout.fillWidth: true
                Layout.leftMargin: 20
                Layout.rightMargin: 20
                Layout.bottomMargin: 20
                title: "What Nitor will never do"
                subtitle: "The scope is deliberately narrow"

                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: "Nitor only sets LED colours. It never changes pump speed, fan speed, fan or pump " +
                          "curves, cooling modes, thermal thresholds or firmware, and it does not control the " +
                          "Kraken's LCD. Those commands are refused in code, not merely left out of the interface."
                }
            }
        }
    }
}
