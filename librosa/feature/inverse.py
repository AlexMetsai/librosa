#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''Feature inversion'''

import numpy as np
import scipy.fftpack

from ..core.spectrum import griffinlim
from ..core.spectrum import db_to_power
from .. import filters
from ..util import nnls


__all__ = ['mel_to_stft', 'mel_to_audio',
           'mfcc_to_mel', 'mfcc_to_audio']


def mel_to_stft(M, sr=22050, n_fft=2048, power=2.0, **kwargs):
    '''Approximate STFT magnitude from a Mel power spectrogram.

    Parameters
    ----------
    M : np.ndarray [shape=(n_mels, n), non-negative]
        The spectrogram as produced by `feature.melspectrogram`

    sr : number > 0 [scalar]
        sampling rate of the underlying signal

    n_fft : int > 0 [scalar]
        number of FFT components in the resulting STFT

    power : float > 0 [scalar]
        Exponent for the magnitude melspectrogram

    kwargs : additional keyword arguments
        Mel filter bank parameters.
        See `librosa.filters.mel` for details


    Returns
    -------
    S : np.ndarray [shape=(n_fft, t), non-negative]
        An approximate linear magnitude spectrogram


    See Also
    --------
    feature.melspectrogram
    core.stft
    filters.mel
    util.nnls


    Examples
    --------
    >>> y, sr = librosa.load(librosa.util.example_audio_file(), duration=5, offset=10)
    >>> S = np.abs(librosa.stft(y))
    >>> mel_spec = librosa.feature.melspectrogram(S=S, sr=sr)
    >>> S_inv = librosa.feature.inverse.mel_to_stft(mel_spec, sr=sr)

    Compare the results visually

    >>> import matplotlib.pyplot as plt
    >>> plt.figure()
    >>> plt.subplot(2,1,1)
    >>> librosa.display.specshow(librosa.amplitude_to_db(S, ref=np.max, top_db=None),
    ...                          y_axis='log', x_axis='time')
    >>> plt.colorbar()
    >>> plt.title('Original STFT')
    >>> plt.subplot(2,1,2)
    >>> librosa.display.specshow(librosa.amplitude_to_db(np.abs(S_inv - S),
    ...                                                  ref=S.max(), top_db=None),
    ...                          vmax=0, y_axis='log', x_axis='time', cmap='magma')
    >>> plt.title('Residual error (dB)')
    >>> plt.colorbar()
    >>> plt.tight_layout()
    >>> plt.show()
    '''

    # Construct a mel basis with dtype matching the input data
    mel_basis = filters.mel(sr, n_fft, n_mels=M.shape[0],
                            dtype=M.dtype,
                            **kwargs)

    # Find the non-negative least squares solution, and apply
    # the inverse exponent.
    # We'll do the exponentiation in-place.
    inverse = nnls(mel_basis, M)
    return np.power(inverse, 1./power, out=inverse)


def mel_to_audio(M, sr=22050, n_fft=2048, hop_length=512, win_length=None,
                 window='hann', center=True, pad_mode='reflect', power=2.0, n_iter=32,
                 length=None, dtype=np.float32, **kwargs):
    """Invert a mel power spectrogram to audio using Griffin-Lim.

    This is primarily a convenience wrapper for:

        >>> S = librosa.feature.inverse.mel_to_stft(M)
        >>> y = librosa.griffinlim(S)

    Parameters
    ----------
    M : np.ndarray [shape=(n_mels, n), non-negative]
        The spectrogram as produced by `feature.melspectrogram`

    sr : number > 0 [scalar]
        sampling rate of the underlying signal

    n_fft : int > 0 [scalar]
        number of FFT components in the resulting STFT

    hop_length : None or int > 0
        The hop length of the STFT.  If not provided, it will default to `n_fft // 4`

    win_length : None or int > 0
        The window length of the STFT.  By default, it will equal `n_fft`

    window : string, tuple, number, function, or np.ndarray [shape=(n_fft,)]
        A window specification as supported by `stft` or `istft`

    center : boolean
        If `True`, the STFT is assumed to use centered frames.
        If `False`, the STFT is assumed to use left-aligned frames.

    pad_mode : string
        If `center=True`, the padding mode to use at the edges of the signal.
        By default, STFT uses reflection padding.

    power : float > 0 [scalar]
        Exponent for the magnitude melspectrogram

    n_iter : int > 0
        The number of iterations for Griffin-Lim

    length : None or int > 0
        If provided, the output `y` is zero-padded or clipped to exactly `length`
        samples.

    dtype : np.dtype
        Real numeric type for the time-domain signal.  Default is 32-bit float.

    kwargs : additional keyword arguments
        Mel filter bank parameters


    Returns
    -------
    y : np.ndarray [shape(n,)]
        time-domain signal reconstructed from `M`

    See Also
    --------
    core.griffinlim
    feature.melspectrogram
    filters.mel
    feature.inverse.mel_to_stft
    """

    stft = mel_to_stft(M, sr=sr, n_fft=n_fft, power=power, **kwargs)

    return griffinlim(stft, n_iter=n_iter, hop_length=hop_length, win_length=win_length,
                      window=window, center=center, dtype=dtype, length=length,
                      pad_mode=pad_mode)


def mfcc_to_mel(mfcc, n_mels=128, dct_type=2, norm='ortho', ref=1.0):
    '''Invert Mel-frequency cepstral coefficients to approximate a Mel power
    spectrogram.

    This inversion proceeds in two steps:

    1. The inverse DCT is applied to the MFCCs
    2. `core.db_to_power` is applied to map the dB-scaled result to a power
    spectrogram


    Parameters
    ----------
    mfcc : np.ndarray [shape=(n_mfcc, n)]
        The Mel-frequency cepstral coefficients

    n_mels : int > 0
        The number of Mel frequencies

    dct_type : None or {1, 2, 3}
        Discrete cosine transform (DCT) type
        By default, DCT type-2 is used.

    norm : None or 'ortho'
        If `dct_type` is `2 or 3`, setting `norm='ortho'` uses an orthonormal
        DCT basis.

        Normalization is not supported for `dct_type=1`.

    ref : number or callable
        Reference power for (inverse) decibel calculation


    Returns
    -------
    M : np.ndarray [shape=(n_mels, n)]
        An approximate Mel power spectrum recovered from `mfcc`


    See Also
    --------
    mfcc
    melspectrogram
    scipy.fftpack.dct
    '''

    logmel = scipy.fftpack.idct(mfcc, axis=0, type=dct_type, norm=norm, n=n_mels)

    return db_to_power(logmel, ref=ref)


def mfcc_to_audio(mfcc, n_mels=128, dct_type=2, norm='ortho', ref=1.0, **kwargs):
    '''Convert Mel-frequency cepstral coefficients to a time-domain audio signal

    This function is primarily a convenience wrapper for the following steps:

        1. Convert mfcc to Mel power spectrum (`mfcc_to_mel`)
        2. Convert Mel power spectrum to time-domain audio (`mel_to_audio`)


    Parameters
    ----------
    mfcc : np.ndarray [shape=(n_mfcc, n)]
        The Mel-frequency cepstral coefficients

    n_mels : int > 0
        The number of Mel frequencies

    dct_type : None or {1, 2, 3}
        Discrete cosine transform (DCT) type
        By default, DCT type-2 is used.

    norm : None or 'ortho'
        If `dct_type` is `2 or 3`, setting `norm='ortho'` uses an orthonormal
        DCT basis.

        Normalization is not supported for `dct_type=1`.

    ref : number or callable
        Reference power for (inverse) decibel calculation

    kwargs : additional keyword arguments
        Parameters to pass through to `mel_to_audio`

    Returns
    -------
    y : np.ndarray [shape=(n)]
        A time-domain signal reconstructed from `mfcc`

    See Also
    --------
    mfcc_to_mel
    mel_to_audio
    feature.mfcc
    core.griffinlim
    scipy.fftpack.dct
    '''
    mel_spec = mfcc_to_mel(mfcc, n_mels=n_mels, dct_type=dct_type, norm=norm, ref=ref)

    return mel_to_audio(mel_spec, **kwargs)
