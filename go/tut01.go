// Basics

package main

import (
	"fmt"
	"sync"
	"time"
)

func learnSlices() {
	// array of size 4
	// var nums [4]int {1,2,3,4}

	var nums []int
	
}

func worker(url string, wg *sync.WaitGroup, resultChan chan string) {
	defer wg.Done()

	// time.Sleep, Network I/O, Channel ops, and Mutexes put the goroutine into a 
	// waiting state. This yields the underlying OS thread back to the Go scheduler 
	// to run other goroutines. It does NOT block the OS thread.
	time.Sleep(time.Millisecond * 50)
	fmt.Printf("image processed: %s\n", url)
	resultChan <- url

	// What if this has heavy calculations
	// start := time.Now()
	// for time.Since(start) < 50*time.Millisecond {
	// 	// tight loop doing math/hashing
	// }

	// Concurrency vs Parallelism
	// Total CPU work = 50,000 * 50ms = 2,500,000ms (2,500 seconds).
	// Real-world time = Total CPU work / Number of CPU Cores.
	// On an 8-core machine: 2500 / 8 = ~312.5 seconds (over 5 minutes).
	// The scheduler cannot magically parallelize beyond physical hardware.
}

func main() {
	var wg sync.WaitGroup
	resultChan := make(chan string, 5) // buffered channel 

	startTime := time.Now()
	wg.Add(5)
	
	go worker("https://example.com/image1.jpg", &wg, resultChan)
	go worker("https://example.com/image2.jpg", &wg, resultChan)
	go worker("https://example.com/image3.jpg", &wg, resultChan)
	go worker("https://example.com/image4.jpg", &wg, resultChan)
	go worker("https://example.com/image5.jpg", &wg, resultChan)

	wg.Wait()
	close(resultChan) 

	for result := range resultChan { // for ranged over a closed channel yields values until the buffer is empty.
		fmt.Printf("Image processed: %s\n", result)
	}

	fmt.Printf("It took %s time\n", time.Since(startTime))
}