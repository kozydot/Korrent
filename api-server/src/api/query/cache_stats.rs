use super::super::get_context;
use async_graphql::{Context, Object, SimpleObject};
use serde::Serialize;
use torrent_search_client::cache::CacheStats;

#[derive(Default)]
pub struct CacheStatsQuery;

#[derive(SimpleObject, Serialize)]
pub struct CacheStatsResponse {
    pub cache_stats: Option<CacheStats>,
    pub cache_enabled: bool,
}

#[Object]
impl CacheStatsQuery {
    /// Get current cache statistics
    async fn cache_stats<'ctx>(
        &self,
        context: &Context<'ctx>,
    ) -> CacheStatsResponse {
        let ctx = get_context(context);
        
        let cache_stats = ctx.torrent_client().cache_stats();
        let cache_enabled = cache_stats.is_some();
        
        CacheStatsResponse {
            cache_stats,
            cache_enabled,
        }
    }
    
    /// Clear the cache (useful for debugging/admin)
    async fn clear_cache<'ctx>(
        &self,
        context: &Context<'ctx>,
    ) -> bool {
        let ctx = get_context(context);
        ctx.torrent_client().clear_cache();
        true
    }
}
