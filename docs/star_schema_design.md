# SalesLens Star Schema Design

## 1. Objectif du modele

Ce document definit le modele analytique cible de SalesLens a partir des CSV nettoyes dans `data/processed/`. Il prepare l'analyse BI des ventes, paiements, livraisons et avis, sans creer PostgreSQL, SQL, Docker, ETL ou Power BI.

Le choix central est de separer les evenements transactionnels ayant des granularites differentes. Les mesures de ventes, paiements et avis ne sont donc pas reunies dans une seule table de faits.

## 2. Principes de modelisation

- Une table de faits represente un evenement mesurable a un grain defini.
- Une dimension decrit le contexte d'analyse : client, produit, vendeur, paiement ou date.
- Les futures tables utiliseront des cles substituts (`*_key`) et conserveront les identifiants Olist comme cles metier auditables.
- `order_id` restera une dimension degeneree dans les faits pour compter les commandes distinctes.
- Les faits ne seront jamais joints directement entre eux. Une comparaison entre domaines passe par des agregats controles au niveau commande.
- Les montants transactionnels restent dans les faits, jamais dans les dimensions.

## 3. Granularite des tables sources

| Source processed | Lignes | Grain observe | Cle candidate / remarque |
|---|---:|---|---|
| `customers_clean.csv` | 99 441 | Un enregistrement client Olist associe a une commande | `customer_id` est unique. `customer_unique_id` a 96 096 valeurs uniques : il est repetable. |
| `orders_clean.csv` | 99 441 | Une commande | `order_id` est unique. |
| `order_items_clean.csv` | 112 650 | Un article dans une commande | `(order_id, order_item_id)` est unique. 9 803 commandes ont plusieurs articles. |
| `order_payments_clean.csv` | 103 886 | Une allocation de paiement d'une commande | `(order_id, payment_sequential)` est unique. 2 961 commandes ont plusieurs paiements; maximum : 29 lignes. |
| `order_reviews_clean.csv` | 99 224 | Un avis pour une commande | `(order_id, review_id)` est unique. `review_id` seul ne l'est pas. 547 commandes ont plusieurs lignes d'avis; maximum : 3. |
| `products_clean.csv` | 32 951 | Un produit | `product_id` est unique. |
| `sellers_clean.csv` | 3 095 | Un vendeur | `seller_id` est unique. |

Les controles ont confirme 0 article, paiement ou avis sans commande correspondante, et 0 article sans produit ou vendeur correspondant.

## 4. Dimensions proposees

### `dim_date` - obligatoire et conforme

**Grain :** une ligne par date calendrier.

**Attributs :** `date_key`, date, annee, trimestre, numero de mois, nom du mois, annee-mois, jour du mois, jour de semaine, nom du jour et indicateur week-end.

**Roles :** date d'achat, approbation, limite d'expedition, remise au transporteur, livraison client, livraison estimee, creation d'avis et reponse a avis.

Une dimension date permet des filtres et periodes coherents. Elle est preferable a des calculs repetes directement sur les timestamps dans Power BI.

### `dim_customer` - obligatoire et conforme

**Grain :** un `customer_id` Olist.

**Cle metier :** `customer_id`.

**Attributs :** `customer_unique_id`, prefixe postal, ville, etat.

`customer_unique_id` reste un attribut : il peut apparaitre sur plusieurs `customer_id`, donc il ne convient pas comme cle unique de cette premiere dimension.

### `dim_product` - obligatoire et conforme

**Grain :** un `product_id`.

**Attributs :** categorie portugaise originale, categorie anglaise, longueurs de texte, nombre de photos, poids et dimensions.

La categorie portugaise est conservee meme lorsqu'une traduction anglaise existe. Les 623 produits sans traduction anglaise restent identifies comme tels.

### `dim_seller` - obligatoire et conforme

**Grain :** un `seller_id`.

**Attributs :** prefixe postal, ville, etat.

### `dim_payment_type` - recommandee, mais petite

**Grain :** un `payment_type`.

Cette dimension documente `credit_card`, `boleto`, `voucher`, `debit_card` et `not_defined`. Elle rend `fact_payments` plus lisible. Son maintien comme simple attribut de fait est une option acceptable pour un premier deploiement compact.

### Dimensions evaluees mais non retenues au premier deploiement

- `dim_geography` : non retenue. Un prefixe postal peut correspondre a plusieurs lignes de geolocalisation; une regle d'agregation doit etre validee avant sa creation.
- `dim_order_status` : optionnelle. `order_status` peut rester un attribut descriptif dans `fact_sales` ou devenir une petite dimension si le vocabulaire doit etre gouverne.
- `dim_order` : non retenue. `order_id` est plus utile comme dimension degeneree; une dimension tres haute cardinalite apporterait peu de contexte supplementaire.

## 5. Tables de faits proposees

### `fact_sales` - fait principal de ventes

**Grain :** une ligne = un article dans une commande.

**Cle naturelle :** `(order_id, order_item_id)`.

**Cle future :** `sales_key` substitut, avec contrainte d'unicite sur la cle naturelle.

**Dimensions liees :** `dim_date` par roles, `dim_customer`, `dim_product`, `dim_seller`; `order_id` est degenere; `order_status` est un attribut descriptif ou une future petite dimension.

**Mesures stockees :** `price`, `freight_value`.

**KPI calcules :**

- chiffre d'affaires produit = `SUM(price)`;
- fret = `SUM(freight_value)`;
- montant combine explicite = `SUM(price + freight_value)`;
- articles vendus = `COUNTROWS(fact_sales)`;
- commandes = `DISTINCTCOUNT(order_id)`;
- panier moyen produit = `SUM(price) / DISTINCTCOUNT(order_id)`.

`price` est la valeur produit et `freight_value` est le fret. Ils restent separes : les additionner sans nommer la mesure confondrait revenu produit et cout de livraison.

### `fact_payments` - fait separe de paiements

**Grain :** une ligne = une allocation de paiement d'une commande.

**Cle naturelle :** `(order_id, payment_sequential)`.

**Cle future :** `payment_key` substitut, avec contrainte d'unicite sur la cle naturelle.

**Dimensions liees :** `purchase_date_key` derive de la commande (ce n'est pas une date de paiement), `customer_key`, `payment_type_key`, et `order_id` degenere.

**Mesure stockee :** `payment_value`.

**Attribut :** `payment_installments`. Il peut etre filtre, moyenne ou distribue, mais ne doit pas etre somme comme un montant.

**KPI calcules :** montant total paye, montant moyen par allocation, commandes distinctes par type, distribution des echeances.

### `fact_reviews` - fait separe d'avis

**Grain :** une ligne = un avis pour une commande.

**Cle naturelle :** `(order_id, review_id)`.

**Cle future :** `review_key` substitut, avec contrainte d'unicite sur la cle naturelle.

**Dimensions liees :** date de creation d'avis, date de reponse, date d'achat et client lorsque utiles; `order_id` est degenere.

**Mesure stockee :** `review_score`.

**Attributs texte :** titre et message de commentaire. Ils sont conserves pour audit ou analyse textuelle future, mais ne sont pas des dimensions ni des KPI.

**KPI calcules :** score moyen, median, distribution, nombre d'avis et commandes distinctes avec avis.

Une commande peut avoir jusqu'a 3 avis. Pour une analyse au niveau commande, une regle doit etre explicite, par exemple la moyenne des scores par `order_id`. Cette regle analytique ne doit pas remplacer les avis source dans `fact_reviews`.

## 6. Cles primaires et etrangeres

| Table cible | Cle primaire future | Cle metier / unicite | Cles etrangeres |
|---|---|---|---|
| `dim_date` | `date_key` | date | aucune |
| `dim_customer` | `customer_key` | `customer_id` | aucune |
| `dim_product` | `product_key` | `product_id` | aucune |
| `dim_seller` | `seller_key` | `seller_id` | aucune |
| `dim_payment_type` | `payment_type_key` | `payment_type` | aucune |
| `fact_sales` | `sales_key` | `(order_id, order_item_id)` | dates, client, produit, vendeur |
| `fact_payments` | `payment_key` | `(order_id, payment_sequential)` | date achat, client, type paiement |
| `fact_reviews` | `review_key` | `(order_id, review_id)` | dates, client optionnel |

## 7. Relations entre les tables

```text
                              dim_date
                    (dates avec plusieurs roles)
                         /        |        \
                        /         |         \
             dim_customer      fact_sales     dim_product
                  |          grain: article        |
                  |          price, freight         |
                  +-------------+-------------------+
                                |
                           dim_seller

dim_date ---- fact_payments ---- dim_payment_type
                  grain: allocation de paiement
                         |
                    dim_customer

dim_date ---- fact_reviews
               grain: avis par commande
                    |
               dim_customer

`order_id` est une dimension degeneree dans les trois faits.
Aucune relation directe fait-a-fait n'est creee.
```

## 8. Mesures principales

| Domaine | Mesure | Definition |
|---|---|---|
| Ventes | Chiffre d'affaires produit | `SUM(fact_sales.price)` |
| Ventes | Fret | `SUM(fact_sales.freight_value)` |
| Ventes | Articles vendus | `COUNTROWS(fact_sales)` |
| Ventes | Commandes | `DISTINCTCOUNT(fact_sales.order_id)` |
| Ventes | Panier moyen produit | `SUM(price) / DISTINCTCOUNT(order_id)` |
| Paiements | Montant paye | `SUM(fact_payments.payment_value)` |
| Paiements | Commandes par type | `DISTINCTCOUNT(fact_payments.order_id)` filtre par type |
| Avis | Score moyen | `AVERAGE(fact_reviews.review_score)` |
| Avis | Commandes avec avis | `DISTINCTCOUNT(fact_reviews.order_id)` |

Le delai de livraison doit etre calcule apres deduplication au niveau commande. Un calcul direct au grain article donnerait plus de poids aux commandes contenant plusieurs articles.

## 9. Risques de double comptage

Les faits ont des granularites differentes : une commande peut avoir plusieurs articles, plusieurs paiements et plusieurs avis.

Une jointure directe entre `fact_sales` et `fact_payments` sur `order_id` cree un produit cartesien dans une commande. Avec 3 articles et 2 paiements, elle cree 6 lignes. `price`, `freight_value` et `payment_value` seraient repetes et les totaux deviendraient faux.

Le meme risque existe avec les avis : 2 articles et 3 avis produisent 6 lignes; le chiffre d'affaires serait repete 3 fois et les avis 2 fois.

Regles BI :

- calculer une mesure additive depuis un seul fait;
- compter les commandes avec `DISTINCTCOUNT(order_id)`;
- pour comparer ventes, paiements et avis, agreger d'abord chaque fait au niveau `order_id`;
- ne pas creer de relation bidirectionnelle ou fait-a-fait dans Power BI.

## 10. Justification des choix

- `fact_sales` au grain article rend exacte l'analyse par produit, categorie et vendeur.
- `fact_payments` reste separe car ses mesures et son grain different des ventes.
- `fact_reviews` reste separe car un avis est un evenement distinct avec ses propres dates.
- `dim_date` est une dimension conforme reutilisable dans tous les domaines.
- Les dimensions portent des attributs descriptifs; les mesures transactionnelles restent dans les faits.

## 11. Limites du modele

- Les dates sont serializees comme texte dans les CSV processed : le futur chargement devra les parser explicitement.
- Les montants sont en BRL, mais le dataset ne fournit ni marge, ni remise, ni taxe explicite, ni cout produit. Le chiffre d'affaires produit n'est donc pas la rentabilite.
- La geolocalisation exige une regle d'agregation avant toute dimension geographique fiable.
- Les avis multiples par commande demandent une regle seulement pour les analyses au grain commande.
- `customer_id` est adapte au grain Olist; `customer_unique_id` reste un attribut recurrent et non une cle unique dans ce premier modele.

## 12. Decisions a valider avant implementation

1. Confirmer que `fact_sales` conserve toutes les dates de commande comme roles de `dim_date`, et pas seulement la date d'achat.
2. Valider si `order_status` reste un attribut de `fact_sales` ou devient une petite dimension.
3. Valider si `dim_payment_type` est creee physiquement ou reste un attribut de `fact_payments` au premier deploiement.
4. Choisir la regle d'analyse au grain commande pour plusieurs avis : moyenne, dernier avis ou analyse exclusivement au grain avis.
5. Definir une regle de geolocalisation avant toute `dim_geography`.
6. Confirmer la convention metier pour le montant produit + fret, sans le presenter comme chiffre d'affaires produit.

## 13. Schema ASCII final recommande

```text
                              dim_date
                    (purchase / approval / delivery /
                     review creation / review answer)
                         /        |        \
                        /         |         \
             dim_customer      fact_sales     dim_product
                  |          1 row = item          |
                  |          price, freight         |
                  +-------------+-------------------+
                                |
                           dim_seller

dim_date ---- fact_payments ---- dim_payment_type
                  1 row = payment allocation
                  payment_value, installments
                         |
                    dim_customer

dim_date ---- fact_reviews
               1 row = review for an order
               review_score
                    |
               dim_customer

order_id is a degenerate dimension in fact_sales, fact_payments and fact_reviews.
No direct fact-to-fact relationship is created.
```
