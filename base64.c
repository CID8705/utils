#define _UNICODE
#ifdef _UNICODE
#define _CRT_NON_CONFORMING_SWPRINTFS
#define CF_CLIPTEXT CF_UNICODETEXT
#else
#define CF_CLIPTEXT CF_TEXT
#endif

#include <errno.h>
#include <locale.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <tchar.h>
#include <windows.h>

typedef struct {
	TCHAR (*paths)[MAX_PATH];
	size_t capacity;
	size_t size;
} DATA;

int search(DATA *data, LPCTSTR path, LPCTSTR ext) {
	if (GetFileAttributes(path) & FILE_ATTRIBUTE_DIRECTORY) {
		TCHAR dir[MAX_PATH];
		TCHAR subpath[MAX_PATH];
		WIN32_FIND_DATA lp;
		HANDLE handle;
		_stprintf(dir, _T("%s\\*"), path);
		handle = FindFirstFile(dir, &lp);
		if (handle != INVALID_HANDLE_VALUE) {
			dir[_tcslen(dir) - 1] = _T('\0');
			do {
				if (_tcscmp(lp.cFileName, _T(".")) != 0 && _tcscmp(lp.cFileName, _T("..")) != 0) {
					_stprintf(subpath, _T("%s%s"), dir, lp.cFileName);
					if (search(data, subpath, ext) != EXIT_SUCCESS) {
						return EXIT_FAILURE;
					}
				}
			} while(FindNextFile(handle, &lp));
			FindClose(handle);
		}
	}
	else {
		LPCTSTR file = _tcsrchr(path, _T('.'));
		if (ext == NULL || file != NULL && _tcscmp(file, ext) == 0) {
			if (data->size >= data->capacity) {
				data->paths = (TCHAR (*)[MAX_PATH])realloc(data->paths, sizeof(TCHAR [MAX_PATH]) * data->capacity * 2);
				if (data->paths == NULL) {
					return EXIT_FAILURE;
				}
				data->capacity *= 2;
			}
			if (_tcslen(path) < MAX_PATH) {
				_tcscpy(data->paths[data->size++], path);
			}
			else {
				errno = ENAMETOOLONG;
				return EXIT_FAILURE;
			}
		}
	}
	return EXIT_SUCCESS;
}

size_t base64_encode(const unsigned char *in, const size_t inlen, LPTSTR out) {
	const TCHAR b64c[64] = _T("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/");
	size_t i = 0;
	size_t outlen = 0;
	for (i = 0; i < inlen; ++i) {
		*out++ = b64c[in[0] >> 2 & 0x3f];
		*out++ = b64c[((in[0] << 4) + (++i < inlen ? in[1] >> 4 : 0)) & 0x3f];
		*out++ = i < inlen ? b64c[((in[1] << 2) + (++i < inlen ? in[2] >> 6 : 0)) & 0x3f] : _T('=');
		*out++ = i < inlen ? b64c[in[2] & 0x3f] : _T('=');
		in += 3;
		outlen += 4;
	}
	*out = _T('\0');
	return outlen + 1;
}

size_t base64_decode(LPCTSTR in, const size_t inlen, unsigned char *out) {
	LPCTSTR b64c = _T("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=");
	unsigned char b64[128];
	size_t i;
	size_t outlen = 0;
	for (i = 0; i < 65; ++i) {
		b64[b64c[i]] = i;
	}
	while (*in != _T('\0')) {
		unsigned char c[4];
		for (i = 0; i < 4; ++i) {
			c[i] = b64[*in++];
		}
		for (i = 0; i < 3; ++i) {
			if (c[i + 1] == 64) {
				break;
			}
			*out++ = (c[i] << (i * 2 + 2) | c[i + 1] >> ((2 - i) * 2)) & 0xff;
			++outlen;
		}
	}
	return outlen;
}

int cwrite(LPCTSTR buff) {
	LPTSTR clip;
	HGLOBAL mem = GlobalAlloc(GHND | GMEM_SHARE, sizeof(TCHAR) * (_tcslen(buff) + 1));
	if (mem != NULL) {
		clip = (LPTSTR)GlobalLock(mem);
		if (clip != NULL) {
			_tcscpy(clip, buff);
			GlobalUnlock(mem);
			if (OpenClipboard(NULL) != 0) {
				EmptyClipboard();
				SetClipboardData(CF_CLIPTEXT, mem);
				CloseClipboard();
			}
		}
		GlobalFree(mem);
	}
	else {
		return EXIT_FAILURE;
	}
	return EXIT_SUCCESS;
}

int _tmain(const int argc, LPCTSTR argv[]) {
	DATA data = { (TCHAR (*)[MAX_PATH])malloc(sizeof(TCHAR [MAX_PATH]) * (argc - 1)), 0, 0 };
	unsigned int i;
	errno = 0;
	_tsetlocale(LC_ALL, _T(""));
	if (data.paths != NULL) {
		data.capacity = argc - 1;
		for (i = 1; i < argc; ++i) {
			LPTSTR path;
			LPCTSTR str = argv[i];
			while (_tcschr(_T("\\/:*?\"<>|"), *str) != NULL) {
				++str;
			}
			path = (LPTSTR)malloc(sizeof(TCHAR) * (_tcslen(str) + 1));
			if (path == NULL) {
				break;
			}
			_tcscpy(path, str);
			while (_tcschr(_T("\\/:*?\"<>|"), path[_tcslen(path) - 1]) != NULL) {
				path[_tcslen(path) - 1] = _T('\0');
			}
			if (_tcslen(str) < MAX_PATH) {
				search(&data, path, NULL);
			}
			else {
				errno = ENAMETOOLONG;
			}
			free(path);
			if (errno != 0) {
				break;
			}
		}
	}
	if (errno == 0) {
		for (i = 0; i < data.size; ++i) {
			size_t size;
			unsigned char *binary;
			TCHAR *base64;
			FILE *fp;
			_tprintf(_T("[%*u/%u] %s\n"), (unsigned char)log10(data.size) + 1, i + 1, data.size, data.paths[i]);
			fp = _tfopen(data.paths[i], _T("rb"));
			if (fp == NULL) {
				break;
			}
			fseek(fp, 0, SEEK_END);
			size = ftell(fp);
			fseek(fp, 0, SEEK_SET);
			binary = (unsigned char *)malloc(sizeof(unsigned char) * size);
			if (binary == NULL) {
				break;
			}
			fread(binary, sizeof(unsigned char), size, fp);
			fclose(fp);
			base64 = (TCHAR *)malloc(sizeof(TCHAR) * (size + 2) / 3 * 4 + 1);
			if (base64 == NULL) {
				break;
			}
			size = base64_encode(binary, size, base64);
			free(binary);
			// binary = (unsigned char *)malloc(sizeof(unsigned char) * _tcslen(base64) / 4 * 3 + 3);
			// if (binary == NULL) {
			// 	break;
			// }
			// size = base64_decode(base64, _tcslen(base64), binary);
			// fp = _tfopen(_T("a.png"), _T("wb"));
			// if (fp == NULL) {
			// 	break;
			// }
			// fwrite(binary, sizeof(unsigned char), size, fp);
			// fclose(fp);
			// free(binary);
			if (cwrite(base64) != EXIT_SUCCESS) {
				break;
			}
			free(base64);
			_tprintf(_T("Done.\n"));
			if (i < data.size - 1) {
				_tsystem(_T("PAUSE"));
			}
		}
	}
	if (data.capacity > 0) {
		free(data.paths);
	}
	if (errno != 0) {
		_ftprintf(stderr, _T("[Errno %d] %s\n"), errno, _tcserror(errno));
	}
	return EXIT_SUCCESS;
}
