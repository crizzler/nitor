// The screen that answers the five questions a user actually has: is my hardware here, which device
// am I controlling, what colour, which effect, which channel.

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

Page {
    id: page

    function effectTooltip(effect) {
        const parts = [effect.group];
        if (!effect.usesColors) {
            parts.push("no colour");
        } else if (effect.minColors === effect.maxColors) {
            parts.push(effect.maxColors + (effect.maxColors === 1 ? " colour" : " colours"));
        } else {
            parts.push(effect.minColors + "–" + effect.maxColors + " colours");
        }
        if (effect.supportsSpeed) {
            parts.push("speed");
        }
        if (effect.supportsDirection) {
            parts.push("direction");
        }
        return parts.join(" · ");
    }

    ScrollView {
        id: scroller
        anchors.fill: parent
        clip: true
        contentWidth: availableWidth

        ColumnLayout {
            width: scroller.availableWidth
            spacing: 16

            RecoveryCard {
                Layout.fillWidth: true
                Layout.leftMargin: 20
                Layout.rightMargin: 20
                Layout.topMargin: 20
                backendMissing: !app.backendAvailable
                backendSummary: app.backendSummary
                backendHint: app.backendHint
                installCommand: app.installCommand
                permissionDenied: app.accessDenied
                permissionHint: app.permissionHint
                onRecheckRequested: app.refresh()
                onCopyRequested: text => app.copyToClipboard(text)
            }

            // Nothing to control (yet): say so plainly instead of showing dead controls.
            Pane {
                Layout.fillWidth: true
                Layout.margins: 20
                visible: app.backendAvailable && !app.ready && !app.busy
                padding: 24

                background: Rectangle {
                    radius: 8
                    color: page.palette.alternateBase
                }

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 8

                    Label {
                        Layout.fillWidth: true
                        text: "No compatible NZXT controller found"
                        font.bold: true
                        visible: !app.hasDevices
                    }

                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        text: app.hasDevices
                              ? "A device was detected, but Nitor cannot control its LEDs. " +
                                "See the Devices page for details."
                              : "Connect an NZXT RGB & Fan Controller or a Kraken Z series cooler, " +
                                "then choose Check again."
                    }

                    Button {
                        text: "Check again"
                        onClicked: app.refresh()
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 20
                Layout.rightMargin: 20
                Layout.bottomMargin: 20
                spacing: 16
                visible: app.ready

                SectionCard {
                    Layout.fillWidth: true
                    title: "Colour"
                    subtitle: app.effectsUseColors
                              ? "The LEDs will show this colour" + (app.brightness < 100 ? " at " + app.brightness + "% brightness" : "")
                              : "The selected effect generates its own colours"

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 20

                        ColorWheel {
                            id: wheel
                            Layout.preferredWidth: 176
                            Layout.preferredHeight: 176
                            enabled: app.effectsUseColors
                            hue: app.colorHue
                            saturation: app.colorSaturation
                            value: app.colorValue
                            borderColor: Qt.rgba(page.palette.text.r, page.palette.text.g, page.palette.text.b, 0.15)
                            onColorPicked: (red, green, blue) => app.setColorComponents(red, green, blue)
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 10

                            ColorSlotRow {
                                Layout.fillWidth: true
                                items: app.colorSlots
                                textColor: page.palette.text
                                onSlotChosen: index => app.selectColorSlot(index)
                            }

                            HexField {
                                Layout.fillWidth: true
                                colorHex: app.colorHex
                                enabled: app.effectsUseColors
                                onCommitted: text => app.setColorHex(text)
                            }

                            PresetSwatches {
                                Layout.fillWidth: true
                                items: app.presets
                                current: app.colorHex
                                textColor: page.palette.text
                                highlightColor: page.palette.highlight
                                enabled: app.effectsUseColors
                                onPicked: name => app.setPreset(name)
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 56
                                radius: 6
                                color: app.previewColor
                                border.width: 1
                                border.color: Qt.rgba(page.palette.text.r, page.palette.text.g, page.palette.text.b, 0.2)

                                Label {
                                    anchors.centerIn: parent
                                    visible: app.brightness < 100 && app.effectsUseColors
                                    text: "sending " + app.effectiveColor
                                    color: app.brightness < 45 ? "#ffffff" : "#101010"
                                    font.family: "monospace"
                                }
                            }
                        }
                    }
                }

                SectionCard {
                    Layout.fillWidth: true
                    title: "Effect"
                    subtitle: "Only effects this controller supports are listed"

                    ComboBox {
                        id: effectBox
                        Layout.fillWidth: true
                        model: app.effects
                        textRole: "label"
                        valueRole: "id"
                        currentIndex: {
                            for (let index = 0; index < app.effects.length; ++index) {
                                if (app.effects[index].id === app.effectId) {
                                    return index;
                                }
                            }
                            return -1;
                        }
                        onActivated: app.selectEffect(currentValue)

                        delegate: ItemDelegate {
                            id: effectRow
                            required property var modelData
                            required property int index

                            width: effectBox.width
                            text: modelData.label
                            highlighted: effectBox.highlightedIndex === index
                            ToolTip.visible: hovered
                            ToolTip.text: page.effectTooltip(modelData)
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 12
                        visible: app.speedAvailable || app.directionAvailable

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 4
                            visible: app.speedAvailable

                            Label {
                                text: "Speed"
                                opacity: 0.65
                            }

                            ComboBox {
                                id: speedBox
                                Layout.fillWidth: true
                                model: app.speeds
                                currentIndex: Math.max(0, app.speeds.indexOf(app.speed))
                                onActivated: app.setSpeed(currentText)
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 4
                            visible: app.directionAvailable

                            Label {
                                text: "Direction"
                                opacity: 0.65
                            }

                            ComboBox {
                                id: directionBox
                                Layout.fillWidth: true
                                model: app.directions
                                currentIndex: Math.max(0, app.directions.indexOf(app.direction))
                                onActivated: app.setDirection(currentText)
                            }
                        }
                    }

                    Label {
                        Layout.fillWidth: true
                        visible: !app.effectsUseColors
                        wrapMode: Text.WordWrap
                        opacity: 0.65
                        text: "This effect produces its own colours, so the colour picker and the " +
                              "brightness control do not apply to it."
                    }
                }

                SectionCard {
                    Layout.fillWidth: true
                    title: "Channel"
                    subtitle: "Each channel drives its own group of LEDs"

                    ComboBox {
                        id: channelBox
                        Layout.fillWidth: true
                        model: app.channels
                        textRole: "label"
                        valueRole: "id"
                        currentIndex: {
                            for (let index = 0; index < app.channels.length; ++index) {
                                if (app.channels[index].id === app.channelId) {
                                    return index;
                                }
                            }
                            return -1;
                        }
                        onActivated: app.selectChannel(currentValue)

                        delegate: ItemDelegate {
                            id: channelRow
                            required property var modelData
                            required property int index

                            width: channelBox.width
                            text: modelData.label
                            highlighted: channelBox.highlightedIndex === index
                            ToolTip.visible: hovered
                            ToolTip.text: modelData.summary
                        }
                    }

                    Label {
                        Layout.fillWidth: true
                        visible: {
                            for (let index = 0; index < app.channels.length; ++index) {
                                if (app.channels[index].id === app.channelId) {
                                    return app.channels[index].summary === "No accessories detected";
                                }
                            }
                            return false;
                        }
                        wrapMode: Text.WordWrap
                        color: "#f8961e"
                        text: "Nothing is detected on this channel. Check that the LED strip or fan " +
                              "is connected and that the controller was initialised after a power loss."
                    }
                }

                SectionCard {
                    Layout.fillWidth: true
                    title: "Brightness"
                    subtitle: app.brightnessAvailable
                              ? "Dims the colour Nitor sends; these controllers have no brightness setting of their own"
                              : "Not applicable to the selected effect"

                    BrightnessSlider {
                        Layout.fillWidth: true
                        brightness: app.brightness
                        effectiveColor: app.effectiveColor
                        enabled: app.brightnessAvailable
                        onMoved: percent => app.setBrightness(percent)
                    }

                    RowLayout {
                        spacing: 8

                        Button {
                            text: "Apply now"
                            onClicked: app.applyNow()
                        }

                        Button {
                            text: "Turn off"
                            onClicked: app.turnOff()
                        }

                        Button {
                            text: "Reset"
                            onClicked: app.resetToDefaults()
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    visible: app.notices.length > 0

                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        opacity: 0.7
                        text: app.notices.join("\n")
                    }
                }
            }
        }
    }
}
