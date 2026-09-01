include $(TOPDIR)/rules.mk

PKG_NAME:=gateway-evidence
PKG_VERSION:=0.1.0
PKG_RELEASE:=2

include $(INCLUDE_DIR)/package.mk

define Package/gateway-evidence
  SECTION:=chirpstack
  CATEGORY:=ChirpStack
  TITLE:=Crash-safe LoRaWAN gateway evidence journal
  DEPENDS:=+curl +ca-bundle
  USERID:=gateway-evidence=451:gateway-evidence=451 gateway-evidence-upload=452:gateway-evidence=451
endef

define Package/gateway-evidence/description
  Durable Concentratord uplink journal and receipt-validating HTTPS/mTLS uploader.
endef

define Package/gateway-evidence/conffiles
/etc/config/gateway-evidence
endef

define Build/Compile
	# Rust binaries are cross-built with the pinned OpenWrt target toolchain and
	# staged under files/usr/bin before this package is compiled.
endef

define Package/gateway-evidence/install
	$(INSTALL_DIR) $(1)/usr/bin
	$(INSTALL_BIN) ./files/usr/bin/gateway-evidence-writer $(1)/usr/bin/gateway-evidence-writer
	$(INSTALL_BIN) ./files/usr/bin/gateway-evidence-uploader $(1)/usr/bin/gateway-evidence-uploader

	$(INSTALL_DIR) $(1)/etc/config
	$(INSTALL_CONF) ./files/etc/config/gateway-evidence $(1)/etc/config/gateway-evidence

	$(INSTALL_DIR) $(1)/etc/init.d
	$(INSTALL_BIN) ./files/etc/init.d/gateway-evidence-writer $(1)/etc/init.d/gateway-evidence-writer
	$(INSTALL_BIN) ./files/etc/init.d/gateway-evidence-uploader $(1)/etc/init.d/gateway-evidence-uploader
endef

$(eval $(call BuildPackage,gateway-evidence))
