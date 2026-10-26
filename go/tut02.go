// Fan in fan out pattern 

package main

import (
	"fmt"
	"sync"
	"time"
)

type Result struct {
	Value string 
	Err error
}

func worker(url string, wg *sync.WaitGroup, resultChan chan Result) {
	defer wg.Done()

	time.Sleep(time.Millisecond * 50)
	fmt.Printf("image processed: %s\n", url)
	resultChan <- Result {Value: url, Err: nil}
}

func main() {
	var wg sync.WaitGroup
	resultChan := make(chan Result, 5) 

	startTime := time.Now()
	wg.Add(5)
	
	for i := 0; i < 5; i++ {
		go worker("https://example.com/image1.jpg", &wg, resultChan)
	}
	
	wg.Wait()
	close(resultChan) 

	for result := range resultChan {
		fmt.Printf("Image processed: %v\n", result.Value)
	}

	fmt.Printf("It took %s time\n", time.Since(startTime))
}