# RAG Pipeline RAM Usage Report

## Total RAM Usage per File (Entire Pipeline)

| File Name | RAM Used (Delta) | Peak RAM | Duration |
|-----------|-----------------|----------|----------|
| PLG-SOP-004-Project | 732.9 MB | 17,537 KB | 34.2 s |
| Guidelines on Development of Artificial Intelligence | 765.8 MB | 22,692 KB | 35.1 s |
| Freelance Policy.docx | 103.6 MB | 25,632 KB | 6.1 s |
| Copy of Freelance Policy.docx | 153.9 MB | 22,298 KB | 11.7 s |
| ITG-SOP-002-Interviewing Guidelines.pdf | 112.8 MB | 22,809 KB | 10.1 s |
| RFL-POL-004-Referral Policy.pdf | 40.8 MB | 28,961 KB | 4.4 s |
| **The Handbook of Data Science and AI.pdf** | **964.9 MB** | **20,068 KB** | **58.9 s** |

## Stage Breakdown - Largest File (The Handbook of Data Science and AI.pdf)

| Stage | RAM Used (Delta) | Peak RAM | Duration |
|-------|-----------------|----------|----------|
| **download** | +389.1 MB | 21,343 KB | 30.4 s |
| **extraction** | +578.5 MB | 28,961 KB | 24.1 s |
| chunking | 0.0 MB | 14,837 KB | 0.3 s |
| embedding | -4.0 MB | 16,225 KB | 3.8 s |
| vectorstore_write | 0.0 MB | 20,068 KB | 0.2 s |
| embed_and_store | -4.0 MB | 20,068 KB | 4.1 s |

## Key Observations

### File Sizes Impact
1. **"The Handbook of Data Science and AI.pdf"** is the largest consumer of RAM at **964.9 MB** total
2. Larger PDFs show significantly higher RAM usage during extraction and processing
3. Document type (PDF vs DOCX) doesn't seem to significantly impact RAM patterns

### Memory Consumption Patterns
1. **Extraction** is the most memory-intensive stage (+578.5 MB for largest file)
2. **Download** stage also consumes significant RAM (+389.1 MB)
3. **Chunking** and **vectorstore_write** stages use minimal RAM (delta ≈ 0)
4. Peak RAM usage occurs during **extraction** (28,961 KB for largest file)

### Performance Insights
1. Processing time correlates with file size
2. Largest file took 58.9 seconds total (almost 1 minute)
3. Multiple files can be processed concurrently (as shown by overlapping memory patterns)

## Recommendations

1. For large files (>500MB), consider processing during off-peak hours
2. Monitor available RAM when processing multiple large documents concurrently
3. The extraction stage is the primary bottleneck for memory usage

---
*Report generated on: 2026-04-21*  
*Data source: RAG memory profiling logs*