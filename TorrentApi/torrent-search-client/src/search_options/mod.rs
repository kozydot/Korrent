pub mod category;
pub mod invalid_option_error;
pub mod movie_options;
pub mod order;
pub mod sort_column;

use self::category::Category;
use self::{order::Order, sort_column::SortColumn};
use getset::Getters;

#[derive(Getters, Clone, Debug)]
#[get = "pub"]
pub struct SearchOptions {
    query: String,
    category: Category,
    sort: SortColumn,
    order: Order,
}

impl SearchOptions {
    pub fn new(query: String, category: Category, sort: SortColumn, order: Order) -> Self {
        Self {
            query,
            category,
            sort,
            order,
        }
    }
}
