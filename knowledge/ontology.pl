% =============================================================================
%  SmartFood AI - ontology and First-Order Logic specification
% -----------------------------------------------------------------------------
%  Predicate dictionary (facts come from the CSV knowledge base or the parsed label)
%
%  Knowledge-base facts                          Meaning
%  ---------------------------------------------------------------------------
%  is_a(X, Y)                 ingredient X is a kind of Y        (ingredient_relations.csv)
%  additive(A)                A is a food additive               (additives.csv)
%  allergen_source(I,A,Rel,S) I contains/may_contain allergen A  (allergen_derivatives.csv)
%  additive_limit(A,C,Perm,Max,S)  permission / max mg/kg of A in category C
%  cat_parent(C, Parent)      category taxonomy                  (food_categories.csv)
%  nutrition_rule(R,N,Op,T,S) threshold on nutrient N per 100 g  (nutrition_rules.csv)
%  nutrition_scope(R,Type,V)  rule scope: category or claim
%  label_rule(R,Req,S), label_scope(R,C)                         (label_rules.csv)
%  interacts_with(A,B,S)      problematic combination            (ingredient_relations.csv)
%  contradicts_claim(I,Cl,S)  ingredient I contradicts claim Cl  (ingredient_relations.csv)
%  regulation_source(Reg,S)   regulation clause backed by source (regulations.csv)
%  known_ingredient(I)        I exists in the knowledge base
%
%  Product facts (asserted per analysis)
%  ---------------------------------------------------------------------------
%  product(P)  product_category(P,C)  ingredient(P,I)  additive_amount(P,A,MgKg)
%  function_declared(P,A)  declared_allergen(P,A)  advisory_allergen(P,A)
%  has_claim(P,Cl)  allergy_profile(P,A)  nutrient(P,N,Value_per_100g)
%
%  Derived (rules.pl)
%  ---------------------------------------------------------------------------
%  has/2  allergen_present/4  effective_limit/6  concern/5  possible_concern/5
%  gap/3  reportable/4
%
%  First-Order Logic axioms  (all variables universally quantified)
%  ---------------------------------------------------------------------------
%  A1  ingredient(p,x) ∧ is_a*(x,y)                      → has(p,y)
%  A2  has(p,i) ∧ allergen_source(i,a,contains)          → allergen_present(p,a)
%  A3  allergy_profile(p,a) ∧ allergen_present(p,a)      → concern(p, allergy_alert, a)
%  A4  allergen_present(p,a) ∧ label_rule(declare_allergens) ∧ ¬declared_allergen(p,a)
%                                                        → concern(p, undeclared_allergen, a)
%  A5  additive_in(p,a) ∧ in_category(p,c) ∧ additive_limit(a,c,no)
%      ∧ ¬∃c'(more_specific(c',c) ∧ additive_limit(a,c'))  → concern(p, additive_not_permitted, a)
%  A6  has_claim(p,k) ∧ contradicts_claim(i,k) ∧ has(p,i) → concern(p, claim_contradiction, k)
%  A7  concern(p,K,s,_,src) ∧ reportable_kind(K) ∧ regulation_source(reg,src)
%                                                        → reportable(p, reg, K, s)
%  Negation is *negation as failure* under the closed-world assumption, evaluated in
%  strata; "unknown" is handled separately through gap/3 and possible_concern/5.
% =============================================================================
:- discontiguous concern/5.
