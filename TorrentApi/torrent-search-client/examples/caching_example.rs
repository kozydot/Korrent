use torrent_search_client::{
    cache::CacheConfig, Category, Order, SearchOptions,
    SortColumn, TorrentClient,
};
use chrono::Duration;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize logging
    env_logger::init();

    // Example 1: Basic client without caching
    println!("=== Basic Client ===");
    let basic_client = TorrentClient::new();
    let search_options = SearchOptions::new(
        "rust programming".to_string(),
        Category::Video,
        SortColumn::Seeders,
        Order::Descending,
    );

    let start = std::time::Instant::now();
    let results = basic_client.search_all(&search_options).await;
    let duration = start.elapsed();
    println!("Basic search took: {:?}", duration);
    println!("Found {} provider responses", results.len());

    // Example 2: Client with caching enabled
    println!("\n=== Client with Caching ===");
    let cache_config = CacheConfig {
        search_ttl: Duration::minutes(10),
        movie_search_ttl: Duration::hours(1),
        max_entries: 500,
        enabled: true,
    };
    let cached_client = TorrentClient::with_cache(cache_config);

    // First search (will be cached)
    let start = std::time::Instant::now();
    let results1 = cached_client.search_all(&search_options).await;
    let duration1 = start.elapsed();
    println!("First search took: {:?}", duration1);

    // Second search (should be from cache)
    let start = std::time::Instant::now();
    let results2 = cached_client.search_all(&search_options).await;
    let duration2 = start.elapsed();
    println!("Cached search took: {:?}", duration2);
    
    if duration2.as_millis() > 0 {
        println!("Cache speedup: {:.2}x", duration1.as_millis() as f64 / duration2.as_millis() as f64);
    } else {
        println!("Cache speedup: Very fast (cached result)");
    }

    // Check cache stats
    if let Some(stats) = cached_client.cache_stats() {
        println!("Cache stats: {:?}", stats);
    }

    // Example 3: Cache management
    println!("\n=== Cache Management ===");
    println!("Cache stats before cleanup: {:?}", cached_client.cache_stats());
    cached_client.evict_expired_cache();
    println!("Cache stats after cleanup: {:?}", cached_client.cache_stats());

    Ok(())
}
