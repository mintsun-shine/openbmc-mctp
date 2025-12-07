SUMMARY = "MCTP Generic Tool"
DESCRIPTION = "D-Bus service to send and receive generic MCTP packets"
LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${COREBASE}/meta/files/common-licenses/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"

SRC_URI = "file://mctp_tool.py \
           file://xyz.openbmc_project.Mctp.Tool.service"

S = "${WORKDIR}"

inherit systemd

SYSTEMD_SERVICE:${PN} = "xyz.openbmc_project.Mctp.Tool.service"

do_install() {
    install -d ${D}${bindir}
    install -m 0755 ${UNPACKDIR}/mctp_tool.py ${D}${bindir}/
    
    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${UNPACKDIR}/xyz.openbmc_project.Mctp.Tool.service ${D}${systemd_system_unitdir}/
}

RDEPENDS:${PN} += "python3-core python3-dbus python3-pygobject"
