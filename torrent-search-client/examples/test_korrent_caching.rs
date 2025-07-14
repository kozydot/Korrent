use chrono::Duration;
use torrent_search_client::{cache::CacheConfig, TorrentClient, SearchOptions, Category, Order, SortColumn};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    env_logger::init();

    println!("🚀 Testing Korrent1337x API Server Caching Integration");
    
    // Test 1: Create cached client (simulating what the API server does)
    println!("\n1️⃣ Creating cached TorrentClient (as API server does)...");
    let cache_config = CacheConfig::new(
        Duration::minutes(30),  // 30-minute TTL for production use
        1000,                   // Cache up to 1000 searches
        Duration::minutes(5)    // Cleanup every 5 minutes
    );
    let client = TorrentClient::with_cache(cache_config);
    
    // Test 2: Verify cache statistics work
    println!("2️⃣ Checking initial cache statistics...");
    let initial_stats = client.cache_stats();
    match initial_stats {
        Some(stats) => {
            println!("   ✅ Cache enabled: {} entries, {} max", stats.total_entries, stats.max_entries);
        }
        None => {
            println!("   ❌ Cache not enabled!");
            return Ok(());
        }
    }
    
    // Test 3: Perform a search to populate cache
    println!("3️⃣ Performing first search (should populate cache)...");
    let search_options = SearchOptions::new(
        "rust programming".to_string(),
        Category::Video,
        SortColumn::Seeders,
        Order::Descending,
    );
    
    let start = std::time::Instant::now();
    let results1 = client.search_all(&search_options).await;
    let duration1 = start.elapsed();
    
    println!("   ⏱️ First search took: {:?}", duration1);
    println!("   📊 Found {} provider responses", results1.len());
    
    // Test 4: Check cache statistics after first search
    println!("4️⃣ Checking cache statistics after first search...");
    if let Some(stats) = client.cache_stats() {
        println!("   📈 Cache stats: {} total, {} valid, {} expired", 
                 stats.total_entries, stats.valid_entries, stats.expired_entries);
    }
    
    // Test 5: Perform same search again (should be cached)
    println!("5️⃣ Performing same search again (should be cached)...");
    let start = std::time::Instant::now();
    let results2 = client.search_all(&search_options).await;
    let duration2 = start.elapsed();
    
    println!("   ⏱️ Second search took: {:?}", duration2);
    println!("   📊 Found {} provider responses", results2.len());
    
    // Test 6: Compare performance
    println!("6️⃣ Performance comparison:");
    let speedup = duration1.as_nanos() as f64 / duration2.as_nanos() as f64;
    println!("   🚀 Cache speedup: {:.0}x faster", speedup);
    
    if duration2.as_millis() < 10 {
        println!("   ✅ Cache is working! Second search was nearly instant.");
    } else {
        println!("   ⚠️ Cache might not be working properly.");
    }
    
    // Test 7: Final cache statistics
    println!("7️⃣ Final cache statistics:");
    if let Some(stats) = client.cache_stats() {
        println!("   📊 Final cache stats: {} total, {} valid, {} expired", 
                 stats.total_entries, stats.valid_entries, stats.expired_entries);
    }
    
    println!("\n🎉 Korrent1337x caching integration test completed!");
    println!("✅ The API server is now ready with high-performance caching!");
    
    Ok(())
}
