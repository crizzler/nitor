// The window shell: a sidebar for navigation, a header for the device, and a footer that always
// says what just happened.

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "pages"
import "components"

ApplicationWindow {
    id: root

    property int currentPage: 0
    readonly property var navigation: ["Lighting", "Devices", "Settings", "About"]

    minimumWidth: 820
    minimumHeight: 560
    title: app.appName
    visible: true

    Component.onCompleted: {
        // Assigned rather than bound, so the window manager stays in charge of resizing.
        width = app.windowWidth;
        height = app.windowHeight;
        app.start();
        app.queryAutostart();
    }

    onClosing: app.saveWindowState(width, height)

    header: ToolBar {
        RowLayout {
            anchors.fill: parent
            spacing: 10

            Label {
                Layout.leftMargin: 4
                text: app.appName
                font.bold: true
                font.pointSize: Math.round(Qt.application.font.pointSize * 1.2)
            }

            Item {
                Layout.fillWidth: true
            }

            Label {
                visible: app.mockMode
                text: "mock device"
                color: "#f8961e"
                padding: 4
                font.pointSize: Math.round(Qt.application.font.pointSize * 0.9)
                ToolTip.visible: mockBadgeHover.hovered
                ToolTip.text: "Development mode: no real hardware is being touched."

                HoverHandler {
                    id: mockBadgeHover
                }
            }

            ComboBox {
                id: deviceBox
                visible: app.devices.length > 0
                Layout.preferredWidth: Math.min(280, implicitWidth)
                model: app.devices
                textRole: "name"
                valueRole: "key"
                enabled: app.devices.length > 1
                currentIndex: {
                    for (let index = 0; index < app.devices.length; ++index) {
                        if (app.devices[index].current) {
                            return index;
                        }
                    }
                    return 0;
                }
                onActivated: app.selectDevice(currentValue)
            }

            Button {
                text: "Refresh"
                onClicked: app.refresh()
            }
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.preferredWidth: 200
            Layout.fillHeight: true
            color: root.palette.alternateBase

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 10
                spacing: 4

                Repeater {
                    model: root.navigation

                    delegate: ItemDelegate {
                        id: navigationItem
                        required property string modelData
                        required property int index

                        Layout.fillWidth: true
                        text: navigationItem.modelData
                        highlighted: root.currentPage === navigationItem.index
                        onClicked: root.currentPage = navigationItem.index
                    }
                }

                Item {
                    Layout.fillHeight: true
                }

                Label {
                    Layout.fillWidth: true
                    Layout.margins: 6
                    wrapMode: Text.WordWrap
                    opacity: 0.55
                    font.pointSize: Math.round(Qt.application.font.pointSize * 0.85)
                    text: app.currentDeviceName.length > 0 ? app.currentDeviceName : "No device"
                }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            StackLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: root.currentPage

                LightingPage {}
                DevicesPage {}
                SettingsPage {}
                AboutPage {}
            }

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: footerContents.implicitHeight + 16
                color: root.palette.alternateBase

                ColumnLayout {
                    id: footerContents
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.margins: 12
                    spacing: 2

                    StatusPill {
                        Layout.fillWidth: true
                        Layout.leftMargin: 12
                        Layout.rightMargin: 12
                        kind: app.statusKind
                        message: app.statusMessage
                        textColor: root.palette.text
                    }

                    Label {
                        Layout.fillWidth: true
                        Layout.leftMargin: 12
                        Layout.rightMargin: 12
                        visible: app.statusHint.length > 0
                        text: app.statusHint
                        wrapMode: Text.WordWrap
                        opacity: 0.75
                        font.pointSize: Math.round(Qt.application.font.pointSize * 0.9)
                    }
                }
            }
        }
    }
}
