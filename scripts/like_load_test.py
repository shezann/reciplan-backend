#!/usr/bin/env python3
"""
Load test script for like service
Can be run manually to stress test the like system
"""

import sys
import os
import time
import asyncio
import aiohttp
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import argparse

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class LikeLoadTester:
    """Load tester for like/unlike endpoints"""
    
    def __init__(self, base_url='http://localhost:5000', auth_token=None):
        self.base_url = base_url.rstrip('/')
        self.auth_token = auth_token
        self.results = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'response_times': [],
            'errors': [],
            'start_time': None,
            'end_time': None
        }
    
    def generate_test_users(self, count):
        """Generate test user IDs"""
        return [f'load_test_user_{i}' for i in range(count)]
    
    def generate_test_recipes(self, count):
        """Generate test recipe IDs"""
        return [f'load_test_recipe_{i}' for i in range(count)]
    
    async def like_recipe_async(self, session, recipe_id, expect_success=True):
        """Async like operation"""
        url = f"{self.base_url}/api/recipes/{recipe_id}/like"
        headers = {}
        if self.auth_token:
            headers['Authorization'] = f'Bearer {self.auth_token}'
        
        start_time = time.time()
        try:
            async with session.post(url, headers=headers) as response:
                response_time = time.time() - start_time
                self.results['response_times'].append(response_time)
                self.results['total_requests'] += 1
                
                if response.status == 200:
                    self.results['successful_requests'] += 1
                    data = await response.json()
                    return {
                        'success': True,
                        'response_time': response_time,
                        'likes_count': data.get('likes_count', 0),
                        'liked': data.get('liked', False)
                    }
                else:
                    self.results['failed_requests'] += 1
                    error_data = await response.text()
                    error_msg = f"HTTP {response.status}: {error_data}"
                    self.results['errors'].append(error_msg)
                    return {
                        'success': False,
                        'response_time': response_time,
                        'error': error_msg
                    }
        
        except Exception as e:
            response_time = time.time() - start_time
            self.results['response_times'].append(response_time)
            self.results['total_requests'] += 1
            self.results['failed_requests'] += 1
            error_msg = f"Request failed: {str(e)}"
            self.results['errors'].append(error_msg)
            return {
                'success': False,
                'response_time': response_time,
                'error': error_msg
            }
    
    async def unlike_recipe_async(self, session, recipe_id):
        """Async unlike operation"""
        url = f"{self.base_url}/api/recipes/{recipe_id}/like"
        headers = {}
        if self.auth_token:
            headers['Authorization'] = f'Bearer {self.auth_token}'
        
        start_time = time.time()
        try:
            async with session.delete(url, headers=headers) as response:
                response_time = time.time() - start_time
                self.results['response_times'].append(response_time)
                self.results['total_requests'] += 1
                
                if response.status == 200:
                    self.results['successful_requests'] += 1
                    data = await response.json()
                    return {
                        'success': True,
                        'response_time': response_time,
                        'likes_count': data.get('likes_count', 0),
                        'liked': data.get('liked', False)
                    }
                else:
                    self.results['failed_requests'] += 1
                    error_data = await response.text()
                    error_msg = f"HTTP {response.status}: {error_data}"
                    self.results['errors'].append(error_msg)
                    return {
                        'success': False,
                        'response_time': response_time,
                        'error': error_msg
                    }
        
        except Exception as e:
            response_time = time.time() - start_time
            self.results['response_times'].append(response_time)
            self.results['total_requests'] += 1
            self.results['failed_requests'] += 1
            error_msg = f"Request failed: {str(e)}"
            self.results['errors'].append(error_msg)
            return {
                'success': False,
                'response_time': response_time,
                'error': error_msg
            }
    
    async def concurrent_likes_test(self, recipe_id, num_concurrent_users=100):
        """Test concurrent likes from multiple users on same recipe"""
        print(f"🚀 Starting concurrent likes test: {num_concurrent_users} users on recipe {recipe_id}")
        
        self.results['start_time'] = time.time()
        
        async with aiohttp.ClientSession() as session:
            # Create concurrent like operations
            tasks = []
            for i in range(num_concurrent_users):
                task = self.like_recipe_async(session, recipe_id)
                tasks.append(task)
            
            # Execute all tasks concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        self.results['end_time'] = time.time()
        
        # Analyze results
        successful_likes = [r for r in results if isinstance(r, dict) and r.get('success')]
        
        print(f"✅ Concurrent likes test completed:")
        print(f"   - Total requests: {self.results['total_requests']}")
        print(f"   - Successful: {self.results['successful_requests']}")
        print(f"   - Failed: {self.results['failed_requests']}")
        
        if successful_likes:
            final_likes_count = successful_likes[-1].get('likes_count', 0)
            print(f"   - Final likes count: {final_likes_count}")
            
            # Verify data integrity
            expected_likes = len(set(range(num_concurrent_users)))  # Should be equal to concurrent users
            if final_likes_count <= num_concurrent_users:
                print(f"   ✅ Data integrity check: {final_likes_count} <= {num_concurrent_users} (expected)")
            else:
                print(f"   ❌ Data integrity issue: {final_likes_count} > {num_concurrent_users}")
        
        return results
    
    async def like_unlike_oscillation_test(self, recipe_id, num_operations=100):
        """Test rapid like/unlike operations"""
        print(f"🔄 Starting like/unlike oscillation test: {num_operations} operations on recipe {recipe_id}")
        
        self.results['start_time'] = time.time()
        
        async with aiohttp.ClientSession() as session:
            tasks = []
            for i in range(num_operations):
                if i % 2 == 0:
                    # Like operation
                    task = self.like_recipe_async(session, recipe_id)
                else:
                    # Unlike operation
                    task = self.unlike_recipe_async(session, recipe_id)
                tasks.append(task)
            
            # Execute all tasks concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        self.results['end_time'] = time.time()
        
        # Analyze final state
        successful_ops = [r for r in results if isinstance(r, dict) and r.get('success')]
        
        print(f"✅ Oscillation test completed:")
        print(f"   - Total requests: {self.results['total_requests']}")
        print(f"   - Successful: {self.results['successful_requests']}")
        print(f"   - Failed: {self.results['failed_requests']}")
        
        if successful_ops:
            final_likes_count = successful_ops[-1].get('likes_count', 0)
            final_liked_state = successful_ops[-1].get('liked', False)
            print(f"   - Final state: liked={final_liked_state}, count={final_likes_count}")
            
            # Verify consistency
            if (final_liked_state and final_likes_count == 1) or (not final_liked_state and final_likes_count == 0):
                print(f"   ✅ Final state is consistent")
            else:
                print(f"   ❌ Final state inconsistency detected")
        
        return results
    
    def print_performance_stats(self):
        """Print detailed performance statistics"""
        if not self.results['response_times']:
            print("No response time data available")
            return
        
        response_times = self.results['response_times']
        total_time = self.results['end_time'] - self.results['start_time']
        
        avg_response_time = sum(response_times) / len(response_times)
        min_response_time = min(response_times)
        max_response_time = max(response_times)
        
        # Calculate percentiles
        sorted_times = sorted(response_times)
        p50 = sorted_times[len(sorted_times) // 2]
        p95 = sorted_times[int(len(sorted_times) * 0.95)]
        p99 = sorted_times[int(len(sorted_times) * 0.99)]
        
        throughput = self.results['total_requests'] / total_time if total_time > 0 else 0
        
        print(f"\n📊 Performance Statistics:")
        print(f"   - Total test time: {total_time:.2f}s")
        print(f"   - Throughput: {throughput:.1f} requests/second")
        print(f"   - Response times:")
        print(f"     • Average: {avg_response_time*1000:.1f}ms")
        print(f"     • Min: {min_response_time*1000:.1f}ms")
        print(f"     • Max: {max_response_time*1000:.1f}ms")
        print(f"     • 50th percentile: {p50*1000:.1f}ms")
        print(f"     • 95th percentile: {p95*1000:.1f}ms")
        print(f"     • 99th percentile: {p99*1000:.1f}ms")
        
        # Error summary
        if self.results['errors']:
            print(f"\n❌ Errors ({len(self.results['errors'])}):")
            error_counts = {}
            for error in self.results['errors']:
                error_counts[error] = error_counts.get(error, 0) + 1
            
            for error, count in error_counts.items():
                print(f"   - {error}: {count} times")


async def main():
    """Main load test function"""
    parser = argparse.ArgumentParser(description='Load test for like service')
    parser.add_argument('--url', default='http://localhost:5000', help='Base URL for the API')
    parser.add_argument('--token', help='JWT token for authentication')
    parser.add_argument('--users', type=int, default=50, help='Number of concurrent users')
    parser.add_argument('--operations', type=int, default=100, help='Number of operations for oscillation test')
    parser.add_argument('--recipe', default='test_recipe_123', help='Recipe ID to test with')
    parser.add_argument('--test', choices=['concurrent', 'oscillation', 'both'], default='both', help='Which test to run')
    
    args = parser.parse_args()
    
    # Create load tester
    tester = LikeLoadTester(base_url=args.url, auth_token=args.token)
    
    print(f"🧪 Like Service Load Test")
    print(f"   - Target URL: {args.url}")
    print(f"   - Recipe ID: {args.recipe}")
    print(f"   - Authentication: {'Enabled' if args.token else 'Disabled'}")
    print("")
    
    try:
        # Run tests based on selection
        if args.test in ['concurrent', 'both']:
            await tester.concurrent_likes_test(args.recipe, args.users)
            
        if args.test in ['oscillation', 'both']:
            if args.test == 'both':
                # Reset results for second test
                tester.results = {k: [] if isinstance(v, list) else 0 if isinstance(v, int) else v 
                                for k, v in tester.results.items()}
            
            await tester.like_unlike_oscillation_test(args.recipe, args.operations)
        
        # Print performance statistics
        tester.print_performance_stats()
        
    except KeyboardInterrupt:
        print("\n🛑 Load test interrupted by user")
    except Exception as e:
        print(f"\n💥 Load test failed: {e}")
        return 1
    
    print(f"\n✅ Load test completed successfully!")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 