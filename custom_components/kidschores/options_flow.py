# File: options_flow.py
"""
Options Flow for the KidsChores integration, managing entities by internal_id.
Handles add/edit/delete operations with entities referenced internally by internal_id.
Ensures consistency and reloads the integration upon changes.
"""

import uuid
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    LOGGER,
    CONF_KIDS,
    CONF_CHORES,
    CONF_BADGES,
    CONF_REWARDS,
    CONF_PENALTIES,
    DOMAIN,
)
from .flow_helpers import (
    build_kid_schema,
    build_chore_schema,
    build_badge_schema,
    build_reward_schema,
    build_penalty_schema,
)


def _ensure_str(value):
    """Convert anything to string safely."""
    if isinstance(value, dict):
        # Attempt to get a known key or fallback
        return str(value.get("value", next(iter(value.values()), "")))
    return str(value)


class KidsChoresOptionsFlowHandler(config_entries.OptionsFlow):
    """
    Options Flow for adding/editing/deleting kids, chores, badges, rewards, and penalties.
    Manages entities via internal_id for consistency and historical data preservation.
    """

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize the options flow."""
        # Removed: self.config_entry = config_entry
        self.config_entry = config_entry  # Deprecated
        self._entry_options = {}
        self._action = None
        self._entity_type = None

    async def async_step_init(self, user_input=None):
        """
        Main menu for the Options Flow:
        Add/Edit/Delete kid, chore, badge, reward, penalty, or done.
        """
        self._entry_options = dict(self.config_entry.options)

        if user_input is not None:
            selection = user_input["menu_selection"]
            if selection.startswith("add_"):
                self._entity_type = selection.replace("add_", "")
                return await getattr(self, f"async_step_add_{self._entity_type}")()
            elif selection.startswith("edit_"):
                self._entity_type = selection.replace("edit_", "")
                return await self.async_step_select_entity(action="edit")
            elif selection.startswith("delete_"):
                self._entity_type = selection.replace("delete_", "")
                return await self.async_step_select_entity(action="delete")
            elif selection == "done":
                return self.async_create_entry(title="Options", data={})

        menu_choices = [
            "add_kid",
            "edit_kid",
            "delete_kid",
            "add_chore",
            "edit_chore",
            "delete_chore",
            "add_badge",
            "edit_badge",
            "delete_badge",
            "add_reward",
            "edit_reward",
            "delete_reward",
            "add_penalty",
            "edit_penalty",
            "delete_penalty",
            "done",
        ]

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("menu_selection"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=menu_choices,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_select_entity(self, user_input=None, action=None):
        """Select an entity (kid, chore, etc.) to edit or delete based on internal_id."""
        if action:
            self._action = action

        entity_dict = self._get_entity_dict()
        entity_names = [data["name"] for data in entity_dict.values()]

        if user_input is not None:
            selected_name = _ensure_str(user_input["entity_name"])
            internal_id = next(
                (
                    eid
                    for eid, data in entity_dict.items()
                    if data["name"] == selected_name
                ),
                None,
            )
            if not internal_id:
                LOGGER.error("Selected entity '%s' not found.", selected_name)
                return self.async_abort(reason="invalid_entity")

            # Store internal_id in context for later use
            self.context["internal_id"] = internal_id

            if self._action == "edit":
                return await getattr(self, f"async_step_edit_{self._entity_type}")()
            elif self._action == "delete":
                return await getattr(self, f"async_step_delete_{self._entity_type}")()

        if not entity_names:
            return self.async_abort(reason=f"no_{self._entity_type}s")

        return self.async_show_form(
            step_id="select_entity",
            data_schema=vol.Schema(
                {
                    vol.Required("entity_name"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=entity_names,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
            description_placeholders={
                "entity_type": self._entity_type,
                "action": self._action,
            },
        )

    def _get_entity_dict(self):
        """Retrieve the appropriate entity dictionary based on entity_type."""
        return self._entry_options.get(
            CONF_KIDS
            if self._entity_type == "kid"
            else CONF_CHORES
            if self._entity_type == "chore"
            else CONF_BADGES
            if self._entity_type == "badge"
            else CONF_REWARDS
            if self._entity_type == "reward"
            else CONF_PENALTIES
            if self._entity_type == "penalty"
            else {},
        )

    # ------------------ ADD ENTITY ------------------
    async def async_step_add_kid(self, user_input=None):
        """Add a new kid."""
        errors = {}
        kids_dict = self._entry_options.setdefault(CONF_KIDS, {})

        if user_input is not None:
            kid_name = user_input["kid_name"].strip()
            ha_user_id = user_input.get("ha_user")

            if any(kid_data["name"] == kid_name for kid_data in kids_dict.values()):
                errors["kid_name"] = "duplicate_kid"
            else:
                internal_id = user_input.get("internal_id", str(uuid.uuid4()))
                kids_dict[internal_id] = {
                    "name": kid_name,
                    "ha_user_id": ha_user_id,
                    "internal_id": internal_id,
                }
                LOGGER.debug("Added kid '%s' with ID: %s", kid_name, internal_id)
                await self._update_and_reload()
                return await self.async_step_init()

        # Retrieve HA users for linking
        users = await self.hass.auth.async_get_users()
        schema = build_kid_schema(
            users=users, default_kid_name="", default_ha_user_id=None
        )
        return self.async_show_form(
            step_id="add_kid", data_schema=schema, errors=errors
        )

    async def async_step_add_chore(self, user_input=None):
        """Add a new chore."""
        errors = {}
        chores_dict = self._entry_options.setdefault(CONF_CHORES, {})

        if user_input is not None:
            chore_name = user_input["chore_name"].strip()
            internal_id = user_input.get("internal_id", str(uuid.uuid4()))

            if any(
                chore_data["name"] == chore_name for chore_data in chores_dict.values()
            ):
                errors["chore_name"] = "duplicate_chore"
            else:
                chores_dict[internal_id] = {
                    "name": chore_name,
                    "default_points": user_input["default_points"],
                    "partial_allowed": user_input["partial_allowed"],
                    "shared_chore": user_input["shared_chore"],
                    "assigned_kids": user_input["assigned_kids"],
                    "description": user_input.get("chore_description", ""),
                    "icon": user_input.get("icon", ""),
                    "recurring_frequency": user_input.get(
                        "recurring_frequency", "none"
                    ),
                    "due_date": (
                        user_input["due_date"].isoformat()
                        if user_input.get("due_date")
                        else None
                    ),
                    "internal_id": internal_id,
                }
                LOGGER.debug("Added chore '%s' with ID: %s", chore_name, internal_id)
                await self._update_and_reload()
                return await self.async_step_init()

        # Use flow_helpers.build_chore_schema, passing current kids
        kids_dict = {
            data["name"]: eid
            for eid, data in self._entry_options.get(CONF_KIDS, {}).items()
        }
        schema = build_chore_schema(kids_dict)
        return self.async_show_form(
            step_id="add_chore", data_schema=schema, errors=errors
        )

    async def async_step_add_badge(self, user_input=None):
        """Add a new badge."""
        errors = {}
        badges_dict = self._entry_options.setdefault(CONF_BADGES, {})

        if user_input is not None:
            badge_name = user_input["badge_name"].strip()
            internal_id = user_input.get("internal_id", str(uuid.uuid4()))

            if any(
                badge_data["name"] == badge_name for badge_data in badges_dict.values()
            ):
                errors["badge_name"] = "duplicate_badge"
            else:
                badges_dict[internal_id] = {
                    "name": badge_name,
                    "threshold_type": user_input["threshold_type"],
                    "threshold_value": user_input["threshold_value"],
                    "icon": user_input.get("icon", ""),
                    "internal_id": internal_id,
                }
                LOGGER.debug("Added badge '%s' with ID: %s", badge_name, internal_id)
                await self._update_and_reload()
                return await self.async_step_init()

        schema = build_badge_schema()
        return self.async_show_form(
            step_id="add_badge", data_schema=schema, errors=errors
        )

    async def async_step_add_reward(self, user_input=None):
        """Add a new reward."""
        errors = {}
        rewards_dict = self._entry_options.setdefault(CONF_REWARDS, {})

        if user_input is not None:
            reward_name = user_input["reward_name"].strip()
            internal_id = user_input.get("internal_id", str(uuid.uuid4()))

            if any(
                reward_data["name"] == reward_name
                for reward_data in rewards_dict.values()
            ):
                errors["reward_name"] = "duplicate_reward"
            else:
                rewards_dict[internal_id] = {
                    "name": reward_name,
                    "cost": user_input["reward_cost"],
                    "description": user_input.get("reward_description", ""),
                    "icon": user_input.get("icon", ""),
                    "internal_id": internal_id,
                }
                LOGGER.debug("Added reward '%s' with ID: %s", reward_name, internal_id)
                await self._update_and_reload()
                return await self.async_step_init()

        schema = build_reward_schema()
        return self.async_show_form(
            step_id="add_reward", data_schema=schema, errors=errors
        )

    async def async_step_add_penalty(self, user_input=None):
        """Add a new penalty."""
        errors = {}
        penalties_dict = self._entry_options.setdefault(CONF_PENALTIES, {})

        if user_input is not None:
            penalty_name = user_input["penalty_name"].strip()
            penalty_points = user_input["penalty_points"]
            internal_id = user_input.get("internal_id", str(uuid.uuid4()))

            if any(
                penalty_data["name"] == penalty_name
                for penalty_data in penalties_dict.values()
            ):
                errors["penalty_name"] = "duplicate_penalty"
            else:
                penalties_dict[internal_id] = {
                    "name": penalty_name,
                    "points": -abs(penalty_points),  # Ensure points are negative
                    "icon": user_input.get("icon", ""),
                    "internal_id": internal_id,
                }
                LOGGER.debug(
                    "Added penalty '%s' with ID: %s", penalty_name, internal_id
                )
                await self._update_and_reload()
                return await self.async_step_init()

        schema = build_penalty_schema()
        return self.async_show_form(
            step_id="add_penalty", data_schema=schema, errors=errors
        )

    # ------------------ EDIT ENTITY ------------------
    async def async_step_edit_kid(self, user_input=None):
        """Edit an existing kid."""
        errors = {}
        kids_dict = self._entry_options.get(CONF_KIDS, {})
        internal_id = self.context.get("internal_id")

        if not internal_id or internal_id not in kids_dict:
            LOGGER.error("Edit kid: Invalid internal_id '%s'.", internal_id)
            return self.async_abort(reason="invalid_kid")

        kid_data = kids_dict[internal_id]

        if user_input is not None:
            new_name = user_input["kid_name"].strip()
            ha_user_id = user_input.get("ha_user")

            # Check for duplicate names excluding current kid
            if any(
                data["name"] == new_name and eid != internal_id
                for eid, data in kids_dict.items()
            ):
                errors["kid_name"] = "duplicate_kid"
            else:
                kid_data["name"] = new_name
                kid_data["ha_user_id"] = ha_user_id
                LOGGER.debug("Edited kid '%s' with ID: %s", new_name, internal_id)
                await self._update_and_reload()
                return await self.async_step_init()

        # Retrieve HA users for linking
        users = await self.hass.auth.async_get_users()
        schema = build_kid_schema(
            users=users,
            default_kid_name=kid_data["name"],
            default_ha_user_id=kid_data.get("ha_user_id"),
            internal_id=internal_id,
        )
        return self.async_show_form(
            step_id="edit_kid", data_schema=schema, errors=errors
        )

    async def async_step_edit_chore(self, user_input=None):
        """Edit an existing chore."""
        errors = {}
        chores_dict = self._entry_options.get(CONF_CHORES, {})
        internal_id = self.context.get("internal_id")

        if not internal_id or internal_id not in chores_dict:
            LOGGER.error("Edit chore: Invalid internal_id '%s'.", internal_id)
            return self.async_abort(reason="invalid_chore")

        chore_data = chores_dict[internal_id]

        if user_input is not None:
            new_name = user_input["chore_name"].strip()

            # Check for duplicate names excluding current chore
            if any(
                data["name"] == new_name and eid != internal_id
                for eid, data in chores_dict.items()
            ):
                errors["chore_name"] = "duplicate_chore"
            else:
                chore_data["name"] = new_name
                chore_data["default_points"] = user_input["default_points"]
                chore_data["partial_allowed"] = user_input["partial_allowed"]
                chore_data["shared_chore"] = user_input["shared_chore"]
                chore_data["assigned_kids"] = user_input["assigned_kids"]
                chore_data["description"] = user_input.get("chore_description", "")
                chore_data["icon"] = user_input.get("icon", "")
                chore_data["recurring_frequency"] = user_input.get(
                    "recurring_frequency", "none"
                )
                chore_data["due_date"] = (
                    user_input["due_date"].isoformat()
                    if user_input.get("due_date")
                    else None
                )
                LOGGER.debug("Edited chore '%s' with ID: %s", new_name, internal_id)
                await self._update_and_reload()
                return await self.async_step_init()

        # Use flow_helpers.build_chore_schema, passing current kids
        kids_dict = {
            data["name"]: eid
            for eid, data in self._entry_options.get(CONF_KIDS, {}).items()
        }
        schema = build_chore_schema(kids_dict, default=chore_data)
        return self.async_show_form(
            step_id="edit_chore", data_schema=schema, errors=errors
        )

    async def async_step_edit_badge(self, user_input=None):
        """Edit an existing badge."""
        errors = {}
        badges_dict = self._entry_options.get(CONF_BADGES, {})
        internal_id = self.context.get("internal_id")

        if not internal_id or internal_id not in badges_dict:
            LOGGER.error("Edit badge: Invalid internal_id '%s'.", internal_id)
            return self.async_abort(reason="invalid_badge")

        badge_data = badges_dict[internal_id]

        if user_input is not None:
            new_name = user_input["badge_name"].strip()

            # Check for duplicate names excluding current badge
            if any(
                data["name"] == new_name and eid != internal_id
                for eid, data in badges_dict.items()
            ):
                errors["badge_name"] = "duplicate_badge"
            else:
                badge_data["name"] = new_name
                badge_data["threshold_type"] = user_input["threshold_type"]
                badge_data["threshold_value"] = user_input["threshold_value"]
                badge_data["icon"] = user_input.get("icon", "")
                LOGGER.debug("Edited badge '%s' with ID: %s", new_name, internal_id)
                await self._update_and_reload()
                return await self.async_step_init()

        schema = build_badge_schema(default=badge_data)
        return self.async_show_form(
            step_id="edit_badge", data_schema=schema, errors=errors
        )

    async def async_step_edit_reward(self, user_input=None):
        """Edit an existing reward."""
        errors = {}
        rewards_dict = self._entry_options.get(CONF_REWARDS, {})
        internal_id = self.context.get("internal_id")

        if not internal_id or internal_id not in rewards_dict:
            LOGGER.error("Edit reward: Invalid internal_id '%s'.", internal_id)
            return self.async_abort(reason="invalid_reward")

        reward_data = rewards_dict[internal_id]

        if user_input is not None:
            new_name = user_input["reward_name"].strip()

            # Check for duplicate names excluding current reward
            if any(
                data["name"] == new_name and eid != internal_id
                for eid, data in rewards_dict.items()
            ):
                errors["reward_name"] = "duplicate_reward"
            else:
                reward_data["name"] = new_name
                reward_data["cost"] = user_input["reward_cost"]
                reward_data["description"] = user_input.get("reward_description", "")
                reward_data["icon"] = user_input.get("icon", "")
                LOGGER.debug("Edited reward '%s' with ID: %s", new_name, internal_id)
                await self._update_and_reload()
                return await self.async_step_init()

        schema = build_reward_schema(default=reward_data)
        return self.async_show_form(
            step_id="edit_reward", data_schema=schema, errors=errors
        )

    async def async_step_edit_penalty(self, user_input=None):
        """Edit an existing penalty."""
        errors = {}
        penalties_dict = self._entry_options.get(CONF_PENALTIES, {})
        internal_id = self.context.get("internal_id")

        if not internal_id or internal_id not in penalties_dict:
            LOGGER.error("Edit penalty: Invalid internal_id '%s'.", internal_id)
            return self.async_abort(reason="invalid_penalty")

        penalty_data = penalties_dict[internal_id]

        if user_input is not None:
            new_name = user_input["penalty_name"].strip()
            penalty_points = user_input["penalty_points"]

            # Check for duplicate names excluding current penalty
            if any(
                data["name"] == new_name and eid != internal_id
                for eid, data in penalties_dict.items()
            ):
                errors["penalty_name"] = "duplicate_penalty"
            else:
                penalty_data["name"] = new_name
                penalty_data["points"] = -abs(
                    penalty_points
                )  # Ensure points are negative
                penalty_data["icon"] = user_input.get("icon", "")
                LOGGER.debug("Edited penalty '%s' with ID: %s", new_name, internal_id)
                await self._update_and_reload()
                return await self.async_step_init()

        # Prepare data for schema (convert points to positive for display)
        display_data = dict(penalty_data)
        display_data["penalty_points"] = abs(display_data["points"])
        schema = build_penalty_schema(default=display_data)
        return self.async_show_form(
            step_id="edit_penalty", data_schema=schema, errors=errors
        )

    # ------------------ DELETE ENTITY ------------------
    async def async_step_delete_kid(self, user_input=None):
        """Delete a kid."""
        kids_dict = self._entry_options.get(CONF_KIDS, {})
        internal_id = self.context.get("internal_id")

        if not internal_id or internal_id not in kids_dict:
            LOGGER.error("Delete kid: Invalid internal_id '%s'.", internal_id)
            return self.async_abort(reason="invalid_kid")

        kid_name = kids_dict[internal_id]["name"]

        if user_input is not None:
            kids_dict.pop(internal_id, None)
            LOGGER.debug("Deleted kid '%s' with ID: %s", kid_name, internal_id)
            await self._update_and_reload()
            return await self.async_step_init()

        return self.async_show_form(
            step_id="delete_kid",
            data_schema=vol.Schema({}),
            description_placeholders={"kid_name": kid_name},
        )

    async def async_step_delete_chore(self, user_input=None):
        """Delete a chore."""
        chores_dict = self._entry_options.get(CONF_CHORES, {})
        internal_id = self.context.get("internal_id")

        if not internal_id or internal_id not in chores_dict:
            LOGGER.error("Delete chore: Invalid internal_id '%s'.", internal_id)
            return self.async_abort(reason="invalid_chore")

        chore_name = chores_dict[internal_id]["name"]

        if user_input is not None:
            chores_dict.pop(internal_id, None)
            LOGGER.debug("Deleted chore '%s' with ID: %s", chore_name, internal_id)
            await self._update_and_reload()
            return await self.async_step_init()

        return self.async_show_form(
            step_id="delete_chore",
            data_schema=vol.Schema({}),
            description_placeholders={"chore_name": chore_name},
        )

    async def async_step_delete_badge(self, user_input=None):
        """Delete a badge."""
        badges_dict = self._entry_options.get(CONF_BADGES, {})
        internal_id = self.context.get("internal_id")

        if not internal_id or internal_id not in badges_dict:
            LOGGER.error("Delete badge: Invalid internal_id '%s'.", internal_id)
            return self.async_abort(reason="invalid_badge")

        badge_name = badges_dict[internal_id]["name"]

        if user_input is not None:
            badges_dict.pop(internal_id, None)
            LOGGER.debug("Deleted badge '%s' with ID: %s", badge_name, internal_id)
            await self._update_and_reload()
            return await self.async_step_init()

        return self.async_show_form(
            step_id="delete_badge",
            data_schema=vol.Schema({}),
            description_placeholders={"badge_name": badge_name},
        )

    async def async_step_delete_reward(self, user_input=None):
        """Delete a reward."""
        rewards_dict = self._entry_options.get(CONF_REWARDS, {})
        internal_id = self.context.get("internal_id")

        if not internal_id or internal_id not in rewards_dict:
            LOGGER.error("Delete reward: Invalid internal_id '%s'.", internal_id)
            return self.async_abort(reason="invalid_reward")

        reward_name = rewards_dict[internal_id]["name"]

        if user_input is not None:
            rewards_dict.pop(internal_id, None)
            LOGGER.debug("Deleted reward '%s' with ID: %s", reward_name, internal_id)
            await self._update_and_reload()
            return await self.async_step_init()

        return self.async_show_form(
            step_id="delete_reward",
            data_schema=vol.Schema({}),
            description_placeholders={"reward_name": reward_name},
        )

    async def async_step_delete_penalty(self, user_input=None):
        """Delete a penalty."""
        penalties_dict = self._entry_options.get(CONF_PENALTIES, {})
        internal_id = self.context.get("internal_id")

        if not internal_id or internal_id not in penalties_dict:
            LOGGER.error("Delete penalty: Invalid internal_id '%s'.", internal_id)
            return self.async_abort(reason="invalid_penalty")

        penalty_name = penalties_dict[internal_id]["name"]

        if user_input is not None:
            penalties_dict.pop(internal_id, None)
            LOGGER.debug("Deleted penalty '%s' with ID: %s", penalty_name, internal_id)
            await self._update_and_reload()
            return await self.async_step_init()

        return self.async_show_form(
            step_id="delete_penalty",
            data_schema=vol.Schema({}),
            description_placeholders={"penalty_name": penalty_name},
        )

    # ------------------ HELPER METHODS ------------------
    async def _update_and_reload(self):
        """Update the config entry options and reload the integration."""
        self.hass.config_entries.async_update_entry(
            self.config_entry, options=self._entry_options
        )
        await self.hass.config_entries.async_reload(self.config_entry.entry_id)
        LOGGER.debug("Options updated and integration reloaded.")
