// Copyright 2022-2023 the openage authors. See copying.md for legal info.

#include "game_entity.h"

#include "gamestate/component/base_component.h"
#include "gamestate/component/internal/position.h"
#include "renderer/stages/world/world_render_entity.h"

namespace openage::gamestate {

GameEntity::GameEntity(entity_id_t id,
                       util::Path &animation_path) :
	id{id},
	animation_path{animation_path},
	components{},
	render_entity{nullptr} {
}

GameEntity::GameEntity(entity_id_t id) :
	id{id},
	components{},
	render_entity{nullptr} {
}

std::shared_ptr<GameEntity> GameEntity::copy(entity_id_t id) {
	auto copy = std::shared_ptr<GameEntity>(new GameEntity(*this));
	copy->set_id(id);

	return copy;
}

entity_id_t GameEntity::get_id() const {
	return this->id;
}

void GameEntity::set_render_entity(const std::shared_ptr<renderer::world::WorldRenderEntity> &entity) {
	this->render_entity = entity;

	this->push_to_render();
}

void GameEntity::add_component(const std::shared_ptr<component::Component> &component) {
	this->components.insert({component->get_type(), component});
}

void GameEntity::push_to_render() {
	if (this->render_entity != nullptr) {
		if (not this->components.contains(component::component_t::POSITION)) {
			return;
		}

		const auto &pos = dynamic_pointer_cast<component::Position>(this->components.at(component::component_t::POSITION))->get_positions();
		const auto &angle = dynamic_pointer_cast<component::Position>(this->components.at(component::component_t::POSITION))->get_angles();
		this->render_entity->update(this->id, pos, angle, this->animation_path);
	}
}

void GameEntity::set_id(entity_id_t id) {
	this->id = id;
}

} // namespace openage::gamestate
