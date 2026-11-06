% =============================================================================
%  SmartFood AI - inference rules (Horn-clause form of the First-Order Logic
%  axioms in ontology.pl).  Standard Prolog syntax; comments beginning "%% [ID]"
%  give each rule an identifier + plain-English description used in explanations.
%  Conventions: P = product, I/A/B = ingredient or additive, C = category,
%               S = source id, R = rule id.  `\+` is negation-as-failure.
% =============================================================================

% ---------------------------------------------------------------- taxonomy --
%% [R-CAT-1] A product belongs to the category it was declared in.
in_category(P, C) :- product_category(P, C).
%% [R-CAT-2] A product also belongs to every ancestor of its category.
in_category(P, A) :- product_category(P, C), cat_ancestor(C, A).
%% [R-CAT-3] Every product belongs to the root category 'all'.
in_category(P, all) :- product(P).
%% [R-CAT-4] Ancestor of a category = its parent, or an ancestor of its parent.
cat_ancestor(C, A) :- cat_parent(C, A).
cat_ancestor(C, A) :- cat_parent(C, B), cat_ancestor(B, A).

% -------------------------------------------------------- ingredient ontology --
%% [R-ING-1] A product has every ingredient on its label.
has(P, X) :- ingredient(P, X).
%% [R-ING-2] A product also has every more general type of its ingredients (is_a closure).
has(P, Y) :- ingredient(P, X), ancestor(X, Y).
%% [R-ING-3] Transitive closure of the is_a relation.
ancestor(X, Y) :- is_a(X, Y).
ancestor(X, Z) :- is_a(X, Y), ancestor(Y, Z).

% --------------------------------------------------------------- allergens ----
%% [R-ALG-1] An allergen is present when a (general or specific) ingredient contains / derives from it.
allergen_present(P, A, I, S) :- has(P, I), allergen_source(I, A, contains, S).
%% [R-ALG-2] An allergen is possibly present when an ingredient may contain it.
allergen_possible(P, A, I, S) :- has(P, I), allergen_source(I, A, may_contain, S).
%% [R-ALG-3] ALERT: a product contains an allergen that is in the consumer's allergy profile.
concern(P, allergy_alert, A, I, S) :- allergy_profile(P, A), allergen_present(P, A, I, S).
%% [R-ALG-4] POSSIBLE: an ingredient may contain a profile allergen and presence is not confirmed.
possible_concern(P, allergy_possible, A, I, S) :- allergy_profile(P, A), allergen_possible(P, A, I, S), \+ allergen_present(P, A, _, _).
%% [R-ALG-5] POSSIBLE: the label carries a 'may contain' advisory for a profile allergen.
possible_concern(P, allergy_possible, A, label_advisory, label) :- allergy_profile(P, A), advisory_allergen(P, A), \+ allergen_present(P, A, _, _).
%% [R-LBL-0] A label rule applies to a product when the product is in the rule's category scope.
label_applies(P, R) :- label_scope(R, C), in_category(P, C).
%% [R-ALG-6] REGULATORY: an allergen is present but the label does not declare it.
concern(P, undeclared_allergen, A, I, S) :- label_applies(P, R), label_rule(R, declare_allergens, S), allergen_present(P, A, I, _), \+ declared_allergen(P, A).

% --------------------------------------------------------------- additives ----
%% [R-ADD-1] An additive is in a product if the product has it (directly or as a specific form of it).
additive_in(P, A) :- has(P, A), additive(A).
%% [R-ADD-2] A limit entry is a candidate when it concerns the additive and a category the product is in.
limit_candidate(P, A, C, Perm, Max, S) :- additive_in(P, A), in_category(P, C), additive_limit(A, C, Perm, Max, S).
%% [R-ADD-3] A limit is overridden when another limit exists for a more specific category.
more_specific_limit(P, A, C) :- additive_in(P, A), in_category(P, C2), additive_limit(A, C2, _, _, _), cat_ancestor(C2, C).
%% [R-ADD-4] CONFLICT RESOLUTION: the effective limit is the one for the most specific category.
effective_limit(P, A, C, Perm, Max, S) :- limit_candidate(P, A, C, Perm, Max, S), \+ more_specific_limit(P, A, C).
%% [R-ADD-5] REGULATORY: the additive is not permitted in this product's category.
concern(P, additive_not_permitted, A, C, S) :- effective_limit(P, A, C, no, _, S).
%% [R-ADD-6] REGULATORY: the declared amount exceeds the maximum permitted level.
concern(P, additive_exceeds_limit, A, C, S) :- effective_limit(P, A, C, yes, Max, S), additive_amount(P, A, V), V > Max.
%% [R-ADD-7] Some permission data exists for this additive in this product's category tree.
additive_limit_known(P, A) :- limit_candidate(P, A, _, _, _, _).
%% [R-ADD-8] UNCERTAINTY: the additive is present but the knowledge base has no permission data for it.
gap(P, additive_no_limit_data, A) :- additive_in(P, A), \+ additive_limit_known(P, A).
%% [R-ADD-9] The function class of an additive is declared if the label states it.
function_declared_for(P, A) :- function_declared(P, A).
function_declared_for(P, A) :- function_declared(P, X), ancestor(X, A).
%% [R-ADD-10] REGULATORY: an additive is listed without its functional class name.
concern(P, missing_label_info, additive_function, A, S) :- label_applies(P, R), label_rule(R, declare_additive_function, S), additive_in(P, A), \+ function_declared_for(P, A).

% ------------------------------------------------------------ interactions ----
%% [R-INT-1] Two ingredients on the label are a known problematic combination.
concern(P, ingredient_interaction, A, B, S) :- interacts_with(A, B, S), has(P, A), has(P, B).

% ------------------------------------------------------------------ claims ----
%% [R-CLM-1] A front-of-pack claim is contradicted by an ingredient in the list (multi-hop through is_a).
concern(P, claim_contradiction, Claim, I, S) :- has_claim(P, Claim), contradicts_claim(I, Claim, S), has(P, I).

% -------------------------------------------------------------- nutrition ----
%% [R-NUT-0] A nutrition rule applies when the product is in its category scope ...
nutrition_applies(P, R) :- nutrition_scope(R, category, C), in_category(P, C).
%% [R-NUT-0b] ... or when the product makes the claim the rule substantiates.
nutrition_applies(P, R) :- nutrition_scope(R, claim, Cl), has_claim(P, Cl).
%% [R-NUT-1] Nutrient is above a 'greater than' threshold.
nutrition_breach(P, R, N, V, S) :- nutrition_rule(R, N, gt, T, S), nutrition_applies(P, R), nutrient(P, N, V), V > T.
%% [R-NUT-2] Nutrient is at or above a threshold.
nutrition_breach(P, R, N, V, S) :- nutrition_rule(R, N, gte, T, S), nutrition_applies(P, R), nutrient(P, N, V), V >= T.
%% [R-NUT-3] Nutrient is below a 'less than' threshold.
nutrition_breach(P, R, N, V, S) :- nutrition_rule(R, N, lt, T, S), nutrition_applies(P, R), nutrient(P, N, V), V < T.
%% [R-NUT-4] Nutrient is at or below a threshold.
nutrition_breach(P, R, N, V, S) :- nutrition_rule(R, N, lte, T, S), nutrition_applies(P, R), nutrient(P, N, V), V =< T.
%% [R-NUT-5] ADVISORY: a category-level nutrition threshold is breached.
concern(P, nutrient_threshold, N, R, S) :- nutrition_breach(P, R, N, _, S), nutrition_scope(R, category, _).
%% [R-NUT-6] REGULATORY: the nutrition values do not substantiate a claim the label makes.
concern(P, claim_unsupported, Cl, N, S) :- nutrition_breach(P, R, N, _, S), nutrition_scope(R, claim, Cl).
%% [R-NUT-7] Helper predicates over declared nutrients.
nutrient_known(P, N) :- nutrient(P, N, _).
%% [R-NUT-7b] Some nutrient value was supplied for the product.
any_nutrient(P) :- nutrient(P, _, _).
%% [R-NUT-8] UNCERTAINTY: a claim-substantiation rule applies but the nutrient value is missing, so the claim cannot be verified.
gap(P, nutrient_missing, N) :- nutrition_scope(R, claim, _), nutrition_applies(P, R), nutrition_rule(R, N, _, _, _), \+ nutrient_known(P, N).
%% [R-LBL-1] POSSIBLE: no nutrition information was supplied although a labelling rule requires it.
possible_concern(P, missing_label_info, nutrition_information, R, S) :- label_applies(P, R), label_rule(R, nutrition_info_present, S), \+ any_nutrient(P).

% ------------------------------------------------- incomplete information ----
%% [R-GAP-1] UNCERTAINTY: an ingredient is not in the knowledge base.
gap(P, unknown_ingredient, I) :- ingredient(P, I), \+ known_ingredient(I).
%% [R-GAP-2] UNCERTAINTY: the product category is not known, so category-specific rules cannot be checked.
has_category(P) :- product_category(P, _).
%% [R-GAP-2b] UNCERTAINTY: no category was resolved for the product.
gap(P, category_unknown, none) :- product(P), \+ has_category(P).
%% [R-GAP-3] UNCERTAINTY: no ingredient list was supplied.
any_ingredient(P) :- ingredient(P, _).
%% [R-GAP-3b] UNCERTAINTY: nothing to analyse.
gap(P, no_ingredients, none) :- product(P), \+ any_ingredient(P).

% ------------------------------------------------------- regulation linking ----
%% [R-REG-1] A concern is REPORTABLE when it is of a regulatory kind and its source is a clause of a known regulation.
reportable(P, Reg, K, Sub) :- concern(P, K, Sub, _, S), reportable_kind(K), regulation_source(Reg, S).

% --------------------------------------------------------- static knowledge ----
severity(allergy_alert, critical).
severity(allergy_possible, medium).
severity(undeclared_allergen, high).
severity(additive_not_permitted, high).
severity(additive_exceeds_limit, high).
severity(claim_unsupported, high).
severity(claim_contradiction, high).
severity(missing_label_info, medium).
severity(ingredient_interaction, medium).
severity(nutrient_threshold, low).

reportable_kind(undeclared_allergen).
reportable_kind(additive_not_permitted).
reportable_kind(additive_exceeds_limit).
reportable_kind(claim_unsupported).
reportable_kind(claim_contradiction).
reportable_kind(missing_label_info).
