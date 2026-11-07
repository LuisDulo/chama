"""Chama-level permissions. Platform staff get none of these automatically."""

MANAGE_CHAMA = "manage_chama"
MANAGE_MEMBERS = "manage_members"
MANAGE_ROLES = "manage_roles"
PROPOSE_RULES = "propose_rules"
APPROVE_RULES = "approve_rules"
RECORD_CONTRIBUTIONS = "record_contributions"
VIEW_FINANCES = "view_finances"
VIEW_AUDIT = "view_audit"

ALL = [MANAGE_CHAMA, MANAGE_MEMBERS, MANAGE_ROLES, PROPOSE_RULES, APPROVE_RULES,
       RECORD_CONTRIBUTIONS, VIEW_FINANCES, VIEW_AUDIT]

CHAIRPERSON = "Chairperson"
SYSTEM_ROLES = {
    CHAIRPERSON: ("Leads the chama. Has every permission.", ALL),
    "Treasurer": ("Handles money and reconciliation.",
                  [RECORD_CONTRIBUTIONS, VIEW_FINANCES, PROPOSE_RULES, APPROVE_RULES]),
    "Secretary": ("Handles membership and records.",
                  [MANAGE_MEMBERS, PROPOSE_RULES, VIEW_AUDIT]),
    "Member": ("An ordinary member.", []),
}
