import { removeBackground } from '@imgly/background-removal';

// DOM Elements
const dropArea = document.getElementById('drop-area');
const fileInput = document.getElementById('file-input');
const loadingArea = document.getElementById('loading-area');
const resultArea = document.getElementById('result-area');
const progressFill = document.getElementById('progress-fill');
const loadingText = document.getElementById('loading-text');
const originalImage = document.getElementById('original-image');
const resultImage = document.getElementById('result-image');
const downloadBtn = document.getElementById('download-btn');
const resetBtn = document.getElementById('reset-btn');

let currentProcessedBlob = null;
let currentOriginalName = 'image';

// Event Listeners for Drag & Drop
['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
  dropArea.addEventListener(eventName, preventDefaults, false);
});

function preventDefaults(e) {
  e.preventDefault();
  e.stopPropagation();
}

['dragenter', 'dragover'].forEach(eventName => {
  dropArea.addEventListener(eventName, () => {
    dropArea.classList.add('dragover');
  }, false);
});

['dragleave', 'drop'].forEach(eventName => {
  dropArea.addEventListener(eventName, () => {
    dropArea.classList.remove('dragover');
  }, false);
});

dropArea.addEventListener('drop', handleDrop, false);
dropArea.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', handleFileSelect);

downloadBtn.addEventListener('click', downloadResult);
resetBtn.addEventListener('click', resetApp);

// Functions
function handleDrop(e) {
  const dt = e.dataTransfer;
  const files = dt.files;
  if (files.length > 0) {
    processFile(files[0]);
  }
}

function handleFileSelect(e) {
  if (e.target.files.length > 0) {
    processFile(e.target.files[0]);
  }
}

async function processFile(file) {
  if (!file.type.startsWith('image/')) {
    alert('画像ファイルを選択してください。');
    return;
  }

  // 元のファイル名（拡張子抜き）を保存
  currentOriginalName = file.name.replace(/\.[^/.]+$/, "");

  // Show Original Image
  const fileUrl = URL.createObjectURL(file);
  originalImage.src = fileUrl;

  // Switch UI to Loading
  dropArea.classList.add('hidden');
  loadingArea.classList.remove('hidden');
  resultArea.classList.add('hidden');
  
  progressFill.style.width = '0%';
  loadingText.innerText = 'AIモデルを準備中... (初回は少し時間がかかります)';

  try {
    const config = {
      model: 'isnet', // フル精度モデルを指定（重いが精度が高い）
      progress: (key, current, total) => {
        const percent = Math.round((current / total) * 100);
        progressFill.style.width = `${percent}%`;
        loadingText.innerText = `処理中... ${percent}%`;
      }
    };

    // Process Background Removal
    const imageBlob = await removeBackground(file, config);
    currentProcessedBlob = imageBlob;

    // Show Result
    const resultUrl = URL.createObjectURL(imageBlob);
    resultImage.src = resultUrl;

    loadingArea.classList.add('hidden');
    resultArea.classList.remove('hidden');

  } catch (error) {
    console.error('Error removing background:', error);
    alert('エラーが発生しました。もう一度お試しください。');
    resetApp();
  }
}

function downloadResult() {
  if (!currentProcessedBlob) return;

  const url = URL.createObjectURL(currentProcessedBlob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `removed_${currentOriginalName}.png`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function resetApp() {
  dropArea.classList.remove('hidden');
  loadingArea.classList.add('hidden');
  resultArea.classList.add('hidden');
  
  if (originalImage.src) URL.revokeObjectURL(originalImage.src);
  if (resultImage.src) URL.revokeObjectURL(resultImage.src);
  
  originalImage.src = '';
  resultImage.src = '';
  currentProcessedBlob = null;
  currentOriginalName = 'image';
  fileInput.value = '';
}
