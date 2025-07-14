use getset::Getters;
use log::info;
use movie_info::MovieInfoClient;
use qbittorrent_api::QbittorrentClient;
use std::sync::Arc;
use tokio::sync::{Mutex, Notify};
use torrent_search_client::{TorrentClient, cache::CacheConfig};
use chrono::Duration;

use super::config::Config;

#[derive(Getters)]
#[get = "pub"]
pub struct Context {
    torrent_client: TorrentClient,
    qbittorrent_client: QbittorrentClient,
    movie_info_client: MovieInfoClient,
    config: Config,
    movie_tracking_enabled: Mutex<bool>,
    movie_tracking_ntfy: Arc<Notify>,
}

impl Context {
    pub fn new(
        qbittorrent_client: QbittorrentClient,
        config: Config,
    ) -> Self {
        // Create cached torrent client with optimized settings for API server
        let cache_config = CacheConfig::new(
            Duration::minutes(30),  // 30-minute TTL for production use
            1000,                   // Cache up to 1000 searches
            Duration::minutes(5)    // Cleanup every 5 minutes
        );
        let torrent_client = TorrentClient::with_cache(cache_config);
        
        info!("Initialized TorrentClient with caching (TTL: 30min, Max entries: 1000)");
        
        Self {
            torrent_client,
            qbittorrent_client,
            movie_info_client: MovieInfoClient::new(),
            config,
            movie_tracking_enabled: Mutex::new(true),
            movie_tracking_ntfy: Arc::new(Notify::new()),
        }
    }

    pub async fn enable_movie_tracking(&self) {
        if !*self.movie_tracking_enabled.lock().await {
            info!("Enabling movie progress tracking");
            *self.movie_tracking_enabled.lock().await = true;
            self.movie_tracking_ntfy.notify_waiters();
        }
    }

    pub async fn disable_movie_tracking(&self) {
        if *self.movie_tracking_enabled.lock().await {
            info!("Disabling movie progress tracking");
            *self.movie_tracking_enabled.lock().await = false;
            self.movie_tracking_ntfy.notify_waiters();
        }
    }
}

pub type ContextPointer = Arc<Context>;
