// Worker pool pattern

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

func worker(jobsChan chan string, wg *sync.WaitGroup, resultChan chan Result) {
	defer wg.Done()

	for job := range jobsChan {
		fmt.Printf("Processing job: %s\n", job)
		time.Sleep(time.Millisecond * 50)
		resultChan <- Result {Value: job, Err: nil}
	}

	fmt.Printf("Worker done")
}

func main() {
	jobs := []string {
		"image_1.png",
		"image_2.png",
		"image_3.png",
		"image_4.png",
		"image_5.png",
		"image_6.png",
		"image_7.png",
		"image_8.png",
		"image_9.png",
		"image_10.png",
		"image_11.png",
		"image_12.png",
		"image_13.png",
		"image_14.png",
		"image_15.png",
		"image_16.png",
		"image_17.png",
		"image_18.png",
		"image_19.png",
		"image_20.png",
	}

	var wg sync.WaitGroup
	resultChan := make(chan Result, 50)
	jobsChan := make(chan string, len(jobs))

	startTime := time.Now()

	// This is problamatic if there are 100000 jobs it will run 100000 goroutine
	// for _, job := range jobs {
	// 	wg.Add(1)
	// 	go worker(job, &wg, resultChan)
	// }

	totalWorkers := 5

	for i:=1; i<=totalWorkers; i++ {
		wg.Add(1)
		go worker(jobsChan, &wg, resultChan)
	}
	
	// Waiting will be done is a separate goroutine. 
	// Closing channel after all jobs are sent
	go func() {
		wg.Wait()
		close(resultChan) 
	}()

	// Sending jobs
	for _, job := range jobs {
		jobsChan <- job
	}

	close(jobsChan)
	
	for result := range resultChan {
		fmt.Printf("Image processed: %v\n", result.Value)
	}

	fmt.Printf("It took %s time\n", time.Since(startTime))
}