// Copyright 2015-2023 the openage authors. See copying.md for legal info.

#include "gui_texture_factory.h"

#include "gui_filled_texture_handles.h"
#include "gui_game_spec_image_provider_impl.h"
#include "gui_texture.h"

namespace openage::gui {

GuiTextureFactory::GuiTextureFactory(GuiGameSpecImageProviderImpl *provider, const QString &id, const QSize &requested_size) :
	texture_handle(),
	texture_handle_user{provider->fill_texture_handle(id, requested_size, &this->texture_handle)} {
}

GuiTextureFactory::~GuiTextureFactory() = default;

QSGTexture *GuiTextureFactory::createTexture(QQuickWindow *window) const {
	Q_UNUSED(window);
	return new GuiTexture{this->texture_handle};
}

int GuiTextureFactory::textureByteCount() const {
	return 0;
}

QSize GuiTextureFactory::textureSize() const {
	return openage::gui::textureSize(this->texture_handle);
}

} // namespace openage::gui
